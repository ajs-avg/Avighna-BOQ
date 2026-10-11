"""File storage: local folder (default) or Supabase Storage (STORAGE_BACKEND=supabase).

Paths stored in job/sheet records are *storage refs*:
  - local:    absolute filesystem path
  - supabase: "sb://<bucket>/<key>"
`resolve(ref)` always returns a local Path (downloading into a cache when remote), so the
pipeline, previews and exports keep working with plain files.
"""
from __future__ import annotations

import logging
import shutil
import threading
from pathlib import Path
from typing import List, Optional

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)
_lock = threading.Lock()
_instance: Optional["Storage"] = None


class Storage:
    def __init__(self) -> None:
        s = get_settings()
        self.backend = s.storage_backend if s.storage_backend in ("local", "supabase") else "local"
        self.cache_dir = s.data_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.buckets = {"uploads": s.supabase_bucket_drawings, "previews": s.supabase_bucket_previews,
                        "exports": s.supabase_bucket_exports}
        if self.backend == "supabase":
            if not (s.supabase_url and s.supabase_service_role_key):
                raise RuntimeError("STORAGE_BACKEND=supabase needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
            self._base = s.supabase_url.rstrip("/") + "/storage/v1"
            self._headers = {"Authorization": f"Bearer {s.supabase_service_role_key}", "apikey": s.supabase_service_role_key}
            self._client = httpx.Client(timeout=120)
            self._ensure_buckets()

    # ------------------------------------------------------------------ public API
    def is_remote(self, ref: str) -> bool:
        return ref.startswith("sb://")

    def store(self, local_path: Path, kind: str, key: str) -> str:
        """Persist a local file under <kind>/<key>; returns the storage ref to keep in the record."""
        if self.backend == "local":
            return str(local_path)
        bucket = self.buckets[kind]
        url = f"{self._base}/object/{bucket}/{key}"
        with open(local_path, "rb") as fh:
            r = self._client.post(url, headers={**self._headers, "x-upsert": "true",
                                                "Content-Type": "application/octet-stream"}, content=fh.read())
        if r.status_code >= 300:
            raise RuntimeError(f"Supabase upload failed ({r.status_code}): {r.text[:200]}")
        # keep the local copy as cache
        cached = self.cache_dir / bucket / key
        cached.parent.mkdir(parents=True, exist_ok=True)
        if cached.resolve() != Path(local_path).resolve():
            shutil.copy2(local_path, cached)
        return f"sb://{bucket}/{key}"

    def resolve(self, ref: Optional[str]) -> Optional[Path]:
        """Local path for a storage ref (downloads once when remote). None when missing."""
        if not ref:
            return None
        if not self.is_remote(ref):
            p = Path(ref)
            return p if p.exists() else None
        bucket, key = ref[5:].split("/", 1)
        cached = self.cache_dir / bucket / key
        if cached.exists():
            return cached
        r = self._client.get(f"{self._base}/object/{bucket}/{key}", headers=self._headers)
        if r.status_code != 200:
            log.warning("Supabase download failed for %s (%s)", ref, r.status_code)
            return None
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(r.content)
        return cached

    def delete_prefix(self, kind: str, prefix: str) -> None:
        """Delete everything under a prefix (a job id) in one bucket / folder."""
        if self.backend == "local":
            return  # local files are deleted by the caller (data_dir/<kind>/<job>)
        bucket = self.buckets[kind]
        keys = self._list(bucket, prefix)
        if keys:
            self._client.request("DELETE", f"{self._base}/object/{bucket}", headers=self._headers, json={"prefixes": keys})
        shutil.rmtree(self.cache_dir / bucket / prefix, ignore_errors=True)

    # ------------------------------------------------------------------ supabase helpers
    def _ensure_buckets(self) -> None:
        for name in set(self.buckets.values()):
            r = self._client.post(f"{self._base}/bucket", headers=self._headers,
                                  json={"id": name, "name": name, "public": False})
            if r.status_code not in (200, 201, 409, 400):
                log.warning("could not ensure bucket %s: %s %s", name, r.status_code, r.text[:120])

    def _list(self, bucket: str, prefix: str) -> List[str]:
        r = self._client.post(f"{self._base}/object/list/{bucket}", headers=self._headers,
                              json={"prefix": prefix, "limit": 1000, "offset": 0})
        if r.status_code != 200:
            return []
        return [f"{prefix}/{o['name']}" for o in r.json() if o.get("name")]


def get_storage() -> Storage:
    global _instance
    with _lock:
        if _instance is None:
            _instance = Storage()
        return _instance


def reset_storage() -> None:  # tests
    global _instance
    with _lock:
        _instance = None
