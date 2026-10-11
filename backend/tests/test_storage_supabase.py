"""Supabase Storage adapter against a fake HTTP server (httpx.MockTransport): upload, download cache, delete."""
from __future__ import annotations

import json

import httpx

from app import storage as st


def _fake_supabase(store: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        assert request.headers.get("authorization") == "Bearer service-key"
        if path == "/storage/v1/bucket":
            return httpx.Response(201, json={"name": json.loads(request.content)["name"]})
        if path.startswith("/storage/v1/object/list/"):
            bucket = path.split("/")[-1]
            prefix = json.loads(request.content)["prefix"]
            names = [k[len(prefix) + 1:] for (b, k) in store if b == bucket and k.startswith(prefix + "/")]
            return httpx.Response(200, json=[{"name": n} for n in names])
        if path.startswith("/storage/v1/object/") and request.method == "POST":
            _, _, _, _, bucket, key = path.split("/", 5)
            store[(bucket, key)] = request.content
            return httpx.Response(200, json={"Key": f"{bucket}/{key}"})
        if path.startswith("/storage/v1/object/") and request.method == "GET":
            _, _, _, _, bucket, key = path.split("/", 5)
            if (bucket, key) in store:
                return httpx.Response(200, content=store[(bucket, key)])
            return httpx.Response(404, json={"error": "not found"})
        if path.startswith("/storage/v1/object/") and request.method == "DELETE":
            bucket = path.split("/")[-1]
            for k in json.loads(request.content)["prefixes"]:
                store.pop((bucket, k), None)
            return httpx.Response(200, json=[])
        return httpx.Response(500, json={"error": f"unexpected {request.method} {path}"})
    return handler


def test_supabase_storage_roundtrip(tmp_path):
    store: dict = {}
    stg = st.Storage.__new__(st.Storage)   # build like __init__ but with the mock transport
    stg.backend = "supabase"
    stg.cache_dir = tmp_path / "cache"
    stg.cache_dir.mkdir()
    stg.buckets = {"uploads": "drawings", "previews": "previews", "exports": "exports"}
    stg._base = "https://proj.supabase.co/storage/v1"
    stg._headers = {"Authorization": "Bearer service-key", "apikey": "service-key"}
    stg._client = httpx.Client(transport=httpx.MockTransport(_fake_supabase(store)))
    stg._ensure_buckets()

    f = tmp_path / "plan.dwg"
    f.write_bytes(b"AC1032fake")
    ref = stg.store(f, "uploads", "job1/plan.dwg")
    assert ref == "sb://drawings/job1/plan.dwg" and ("drawings", "job1/plan.dwg") in store
    assert stg.resolve(ref).read_bytes() == b"AC1032fake"            # served from cache
    (tmp_path / "cache" / "drawings" / "job1" / "plan.dwg").unlink()
    assert stg.resolve(ref).read_bytes() == b"AC1032fake"            # re-downloaded
    assert stg.resolve("sb://drawings/job1/missing.dwg") is None
    assert stg.resolve(str(f)) == f and stg.resolve(None) is None
    stg.delete_prefix("uploads", "job1")
    assert ("drawings", "job1/plan.dwg") not in store
