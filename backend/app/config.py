"""Runtime configuration, read from environment variables (.env supported)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

try:  # optional, keeps local runs convenient
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


def _bool(v: Optional[str], default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    """Plain class (no pydantic-settings dependency) so it imports anywhere."""

    def __init__(self) -> None:
        self.app_name: str = "Avighna BOQ API"
        self.env: str = os.getenv("APP_ENV", "development")
        self.port: int = int(os.getenv("PORT", "8000"))
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")

        # Repo layout: <root>/backend (this app), <root>/database (sqlite + schema), <root>/samples
        self.repo_root: Path = Path(__file__).resolve().parents[2]
        self.database_dir: Path = Path(os.getenv("DATABASE_DIR", str(self.repo_root / "database"))).resolve()
        # Where uploaded files, previews and exports live (job-id keyed sub-folders)
        self.data_dir: Path = Path(os.getenv("DATA_DIR", str(self.repo_root / "backend" / "data"))).resolve()
        self.storage_backend: str = os.getenv("STORAGE_BACKEND", "local")  # local only in this build
        self.auth_mode: str = os.getenv("AUTH_MODE", "local")  # local (JWT + sqlite users)
        self.db_path: Path = Path(os.getenv("DB_PATH", str(self.database_dir / "boq.db"))).resolve()
        # Postgres / Supabase when set (postgresql://user:pass@host:5432/postgres); SQLite otherwise
        self.database_url: str = os.getenv("DATABASE_URL", "").strip()

        # Local auth
        self.jwt_secret: str = os.getenv("JWT_SECRET", "")
        self.jwt_expires_hours: int = int(os.getenv("JWT_EXPIRES_HOURS", "12"))
        self.bootstrap_admin_email: str = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@avighnagroup.com").strip().lower()
        self.bootstrap_admin_password: str = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
        self.bootstrap_admin_name: str = os.getenv("BOOTSTRAP_ADMIN_NAME", "Avighna Admin")

        # Supabase (service role is used ONLY on the server)
        self.supabase_url: str = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")
        self.supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self.supabase_bucket_drawings: str = os.getenv("SUPABASE_BUCKET_DRAWINGS", "drawings")
        self.supabase_bucket_previews: str = os.getenv("SUPABASE_BUCKET_PREVIEWS", "previews")
        self.supabase_bucket_exports: str = os.getenv("SUPABASE_BUCKET_EXPORTS", "exports")

        # Gemini
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
        # "auto" = pick the newest available model from the API at startup (see app/ai/gemini.py)
        self.gemini_model_fast: str = os.getenv("GEMINI_MODEL_FAST", "auto")
        self.gemini_model_pro: str = os.getenv("GEMINI_MODEL_PRO", "auto")
        self.gemini_timeout_s: int = int(os.getenv("GEMINI_TIMEOUT_S", "180"))
        self.gemini_max_image_px: int = int(os.getenv("GEMINI_MAX_IMAGE_PX", "3000"))
        self.ai_enabled: bool = _bool(os.getenv("AI_ENABLED"), default=bool(self.gemini_api_key))

        # DWG conversion
        self.oda_converter_bin: str = os.getenv("ODA_CONVERTER_BIN", "ODAFileConverter")
        # Candidate dwg2dxf binaries, best first: locally built 0.13.x, conda 0.11, anything on PATH.
        _home = Path.home()
        self.libredwg_candidates: List[str] = [
            os.getenv("LIBREDWG_BIN", ""),
            str(_home / ".local" / "opt" / "libredwg-0.13.4" / "bin" / "dwg2dxf"),
            "/opt/anaconda3/envs/dwgtools/bin/dwg2dxf",
            "dwg2dxf",
        ]
        self.libredwg_candidates = [c for i, c in enumerate(self.libredwg_candidates) if c and c not in self.libredwg_candidates[:i]]
        self.libredwg_bin: str = next((c for c in self.libredwg_candidates if os.path.exists(c)), self.libredwg_candidates[-1])
        self.conversion_timeout_s: int = int(os.getenv("CONVERSION_TIMEOUT_S", "300"))

        # Web
        origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
        self.cors_origins: List[str] = [o.strip() for o in origins.split(",") if o.strip()]
        # Regex for additional allowed origins. Default covers Vercel preview/production URLs and
        # Render; safe because the API uses bearer tokens (no cookie auth), so CORS only gates XHR.
        self.cors_origin_regex: str = os.getenv("CORS_ORIGIN_REGEX", r"^https://[a-z0-9-]+\.(vercel\.app|onrender\.com)$")
        self.frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
        self.max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "200"))
        self.max_pages: int = int(os.getenv("MAX_PAGES", "150"))  # per PDF; later pages are skipped with a note
        self.worker_threads: int = int(os.getenv("WORKER_THREADS", "2"))
        self.preview_dpi: int = int(os.getenv("PREVIEW_DPI", "110"))

        # First admin bootstrap: comma separated emails that are promoted to admin on first login
        self.bootstrap_admin_emails: List[str] = [
            e.strip().lower() for e in os.getenv("BOOTSTRAP_ADMIN_EMAILS", "").split(",") if e.strip()
        ]

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("uploads", "work", "previews", "exports"):
        (s.data_dir / sub).mkdir(parents=True, exist_ok=True)
    if not s.jwt_secret:
        # persist a random secret so tokens survive restarts without any config
        secret_file = s.data_dir / ".jwt_secret"
        if secret_file.exists():
            s.jwt_secret = secret_file.read_text().strip()
        else:
            import secrets
            s.jwt_secret = secrets.token_urlsafe(48)
            secret_file.write_text(s.jwt_secret)
            try:
                os.chmod(secret_file, 0o600)
            except OSError:
                pass
    return s
