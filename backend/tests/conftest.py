import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_tmp = Path(tempfile.mkdtemp(prefix="avighna_test_"))
os.environ.setdefault("DATA_DIR", str(_tmp / "data"))
os.environ.setdefault("DB_PATH", str(_tmp / "boq-test.db"))
os.environ.setdefault("BOOTSTRAP_ADMIN_EMAIL", "admin@test.local")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "Test-Admin-123")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("WORKER_THREADS", "1")
os.environ.setdefault("PREVIEW_DPI", "40")
os.environ.setdefault("GEMINI_MAX_IMAGE_PX", "1200")

# Run the same suite on an embedded PostgreSQL when TEST_POSTGRES=1 (see tools/test_postgres.sh).
# The server must live inside the pytest process, so it is started here and kept referenced.
if os.environ.get("TEST_POSTGRES") and not os.environ.get("DATABASE_URL"):
    import atexit
    import pgserver  # type: ignore

    _PG = pgserver.get_server(str(_tmp / "pg"))
    os.environ["DATABASE_URL"] = _PG.get_uri()
    atexit.register(lambda: _PG.cleanup())
