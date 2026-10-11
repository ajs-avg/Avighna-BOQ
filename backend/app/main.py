"""Avighna BOQ API - FastAPI application (local build)."""
from __future__ import annotations

import json
import logging
import logging.handlers
import shutil
import tempfile
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from app import auth, db, repository as repo
from app.storage import get_storage
from app.sysinfo import max_dxf_mb, memory_limit_mb
from app.ai.gemini import GeminiClient, ai_status
from app.config import get_settings
from app.extract.dwg_convert import converter_status
from app.models.schemas import (
    AIStatus, CreateJobResponse, FitoutItem, InviteRequest, InviteResponse, ItemUpdate, JobEvent, JobRecord,
    ElementsUpdate, JobStatus, LoginRequest, MeasurementExtraction, MemberSpec, MemberUpdate, Module, RoleUpdate,
    SetPasswordRequest, SheetRecord, SourceFile, Standards, TokenResponse, UserProfile, new_id,
)
from app.engine.measurement import compute_measurement
from app.pipeline import Pipeline, recalculate

VERSION = "1.2.3"
log = logging.getLogger("app")
_member_adapter = TypeAdapter(MemberSpec)
IN_FLIGHT = (JobStatus.queued, JobStatus.converting, JobStatus.analysing, JobStatus.extracting, JobStatus.quantifying)
EDITABLE = (JobStatus.ready, JobStatus.approved, JobStatus.failed)


# ----------------------------------------------------------------------------- startup
def _setup_logging() -> None:
    s = get_settings()
    root = logging.getLogger()
    root.setLevel(getattr(logging, s.log_level.upper(), logging.INFO))
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)
    logs = s.data_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        fh = logging.handlers.RotatingFileHandler(logs / "api.log", maxBytes=5_000_000, backupCount=5)
        fh.setFormatter(fmt)
        root.addHandler(fh)
    logging.getLogger("ezdxf").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _recover_in_flight_jobs() -> None:
    """Jobs interrupted by a restart are re-queued instead of hanging forever."""
    items, _ = repo.list_jobs(limit=200, offset=0)
    for it in items:
        if it.status in IN_FLIGHT:
            job = repo.get_job(it.id)
            if job is None:
                continue
            restarts = sum(1 for e in job.events if e.message.startswith("Server restarted"))
            if restarts >= 2:   # the same job took the server down twice: almost certainly out of memory
                job.status, job.progress = JobStatus.failed, 0
                job.error = ("Processing stopped: this drawing crashed the server twice (most likely out of memory). "
                             "Upload a PDF plot or a lighter DXF export, split the drawing, or move the API to a "
                             "bigger instance (2 GB recommended).")
                job.events.append(JobEvent(at=datetime.utcnow(), status=JobStatus.failed, message=job.error, progress=0))
                repo.save_job(job)
                log.error("job %s marked failed after %d server restarts", job.id, restarts)
                continue
            job.status, job.progress = JobStatus.queued, 0
            job.events.append(JobEvent(at=datetime.utcnow(), status=JobStatus.queued,
                                       message="Server restarted - job re-queued automatically", progress=0))
            repo.save_job(job)
            Pipeline.get().submit(job.id)
            log.warning("re-queued interrupted job %s", job.id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    _setup_logging()
    db.connect()
    auth.bootstrap_admin()
    GeminiClient.get()
    Pipeline.get()
    _recover_in_flight_jobs()
    log.info("Avighna BOQ API %s ready. db=%s data=%s ai=%s", VERSION, s.db_path, s.data_dir, ai_status().message)
    yield


app = FastAPI(title="Avighna BOQ API", version=VERSION, lifespan=lifespan,
              description="Drop a drawing, get a measurement sheet. Structural BBS + interior fit-out BOQ.")
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins,
                   allow_origin_regex=get_settings().cors_origin_regex or None, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"], expose_headers=["Content-Disposition"])


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"Internal error: {type(exc).__name__}"})


# ----------------------------------------------------------------------------- login throttle
class _Throttle:
    """8 failed logins per email within 10 minutes -> 60 s lock. In-memory (single local server)."""

    def __init__(self) -> None:
        self.fails: Dict[str, List[float]] = {}
        self.lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.time()
        with self.lock:
            hist = [t for t in self.fails.get(key, []) if now - t < 600]
            self.fails[key] = hist
            if len(hist) >= 8 and now - hist[-1] < 60:
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts. Try again in a minute.")

    def failed(self, key: str) -> None:
        with self.lock:
            self.fails.setdefault(key, []).append(time.time())

    def ok(self, key: str) -> None:
        with self.lock:
            self.fails.pop(key, None)


_throttle = _Throttle()


# ----------------------------------------------------------------------------- health / auth
@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    st = ai_status()
    return {"status": "ok", "version": VERSION, "converters": converter_status(), "ai": st.model_dump(),
            "gemini_model": st.model_pro, "memory_limit_mb": memory_limit_mb(), "max_dxf_mb": max_dxf_mb()}


@app.get("/api/v1/system")
def system(user: UserProfile = Depends(auth.current_user)) -> Dict[str, Any]:
    s = get_settings()
    stats = repo.job_stats()

    def _dir_mb(p: Path) -> float:
        try:
            return round(sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e6, 1)
        except OSError:
            return 0.0
    return {
        "version": VERSION, "ai": ai_status().model_dump(), "converters": converter_status(),
        "libredwg_bin": s.libredwg_bin, "db_path": str(s.db_path), "data_dir": str(s.data_dir),
        "db_backend": db.backend(), "storage_backend": get_storage().backend,
        "db_mb": round(s.db_path.stat().st_size / 1e6, 2) if (db.backend() == "sqlite" and s.db_path.exists()) else 0.0,
        "data_mb": _dir_mb(s.data_dir), "worker_threads": s.worker_threads, "max_upload_mb": s.max_upload_mb,
        "memory_limit_mb": memory_limit_mb(), "max_dxf_mb": max_dxf_mb(),
        "stats": stats, "users": repo.count_users(),
    }


@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login(req: LoginRequest) -> TokenResponse:
    key = req.email.strip().lower()
    _throttle.check(key)
    try:
        tok = auth.login(req)
    except HTTPException as exc:
        if exc.status_code == 401:
            _throttle.failed(key)
            db.audit("login.failed", key)
        raise
    _throttle.ok(key)
    db.audit("login", tok.profile.email)
    return tok


@app.post("/api/v1/auth/set-password", response_model=UserProfile)
def set_password(req: SetPasswordRequest, user: UserProfile = Depends(auth.current_user)) -> UserProfile:
    out = auth.set_password(user, req)
    db.audit("password.set", user.email)
    return out


@app.get("/api/v1/me", response_model=UserProfile)
def me(user: UserProfile = Depends(auth.current_user)) -> UserProfile:
    return user


@app.get("/api/v1/ai/status", response_model=AIStatus)
def get_ai_status(_: UserProfile = Depends(auth.current_user)) -> AIStatus:
    return ai_status()


@app.get("/api/v1/stats")
def stats(_: UserProfile = Depends(auth.current_user)) -> Dict[str, Any]:
    return repo.job_stats()


# ----------------------------------------------------------------------------- jobs
def _load_job(job_id: str) -> JobRecord:
    job = repo.get_job(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


def _require_editable(job: JobRecord) -> None:
    if job.status not in EDITABLE:
        raise HTTPException(status.HTTP_409_CONFLICT, "Job is still processing; wait until it is ready")


def _safe_name(name: str) -> str:
    keep = "".join(ch if (ch.isalnum() or ch in "._- ()") else "_" for ch in Path(name).name)
    return keep.strip() or "file"


def _format_from_ext(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    if ext == "dwg":
        return "dwg"
    if ext == "dxf":
        return "dxf"
    if ext == "pdf":
        return "pdf"
    if ext in ("png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp"):
        return "image"
    return "unknown"


def _event(job: JobRecord, st: JobStatus, message: str, progress: Optional[int] = None) -> None:
    job.events.append(JobEvent(at=datetime.utcnow(), status=st, message=message,
                               progress=job.progress if progress is None else progress))


@app.post("/api/v1/jobs", response_model=CreateJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    files: List[UploadFile] = File(...),
    module: str = Form("measurement"),
    project_name: str = Form(...),
    level: str = Form(""),
    contractor: Optional[str] = Form(None),
    drawn_by: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    currency: Optional[str] = Form(None),
    standards: Optional[str] = Form(None),
    user: UserProfile = Depends(auth.current_user),
) -> CreateJobResponse:
    s = get_settings()
    try:
        mod = Module(module)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "module must be 'measurement', 'structural' or 'fitout'")
    files = [f for f in files if f.filename]
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Upload at least one drawing file")
    std = repo.get_standards()
    if standards:
        try:
            std = Standards.model_validate(json.loads(standards))
        except (ValueError, ValidationError) as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid standards JSON: {exc}")
    job = JobRecord(id=new_id(), module=mod, project_name=project_name.strip() or "Untitled project",
                    level=level.strip() or ("All levels" if mod == Module.fitout else "Level"),
                    contractor=(contractor or "").strip() or None, drawn_by=(drawn_by or "").strip() or None,
                    location=(location or "").strip() or None,
                    currency=(currency or ("AED" if mod == Module.fitout else "INR")).upper()[:4],
                    standards=std, created_by=user.id, created_by_email=user.email)
    if mod == Module.fitout:
        job.work_description = "Interior fit-out works: supply and installation complete as per drawings and specifications"
    elif mod == Module.measurement:
        job.work_description = "Measurement sheet, BOQ abstract and material requirement from drawings (IS 1200)"
    updir = s.data_dir / "uploads" / job.id
    updir.mkdir(parents=True, exist_ok=True)
    limit = s.max_upload_mb * 1024 * 1024
    seen = set()
    for uf in files:
        name = _safe_name(uf.filename or "file")
        if name in seen:  # same file name twice -> keep both
            name = f"{Path(name).stem}_{len(seen)}{Path(name).suffix}"
        seen.add(name)
        dest = updir / name
        size = 0
        with open(dest, "wb") as fh:
            while True:
                chunk = await uf.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    fh.close()
                    shutil.rmtree(updir, ignore_errors=True)
                    raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"{name} exceeds {s.max_upload_mb} MB")
                fh.write(chunk)
        if size == 0:
            dest.unlink(missing_ok=True)
            continue
        ref = get_storage().store(dest, "uploads", f"{job.id}/{name}")
        job.source_files.append(SourceFile(name=name, size_bytes=size, format=_format_from_ext(dest),  # type: ignore[arg-type]
                                           storage_path=ref, mime=uf.content_type or "application/octet-stream"))
    if not job.source_files:
        shutil.rmtree(updir, ignore_errors=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "All uploaded files were empty")
    _event(job, JobStatus.queued, f"Job created by {user.email} with {len(job.source_files)} file(s)", 0)
    repo.save_job(job)
    db.audit("job.create", user.email, job.id, f"{mod.value}: {job.project_name} / {job.level}")
    Pipeline.get().submit(job.id)
    return CreateJobResponse(job_id=job.id, status=job.status)


@app.get("/api/v1/jobs")
def list_jobs(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
              module: Optional[str] = None, status_: Optional[str] = Query(None, alias="status"),
              _: UserProfile = Depends(auth.current_user)) -> Dict[str, Any]:
    if module and module not in ("measurement", "structural", "fitout"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "module must be 'measurement', 'structural' or 'fitout'")
    if status_ and status_ not in {s.value for s in JobStatus}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown status")
    items, total = repo.list_jobs(limit, offset, module, status_)
    return {"items": [i.model_dump() for i in items], "total": total}


@app.get("/api/v1/jobs/{job_id}", response_model=JobRecord)
def get_job(job_id: str, _: UserProfile = Depends(auth.current_user)) -> JobRecord:
    job = _load_job(job_id)
    if (job.module == Module.measurement and job.measurement and job.elements and job.elements.rooms
            and not job.measurement.room_breakdown):
        # results saved before the room-wise view existed: recompute on read (cheap, deterministic, not saved)
        job.measurement = compute_measurement(job.elements)
    return job


@app.get("/api/v1/jobs/{job_id}/sheets", response_model=List[SheetRecord])
def get_sheets(job_id: str, _: UserProfile = Depends(auth.current_user)) -> List[SheetRecord]:
    _load_job(job_id)
    out = []
    for sh in repo.get_sheets(job_id):
        sh.extraction = None
        sh.fitout_extraction = None
        out.append(sh)
    return out


@app.get("/api/v1/jobs/{job_id}/sheets/{sheet_id}/extraction")
def get_sheet_extraction(job_id: str, sheet_id: str, _: UserProfile = Depends(auth.current_user)) -> Dict[str, Any]:
    """Raw per-sheet reading (what the AI / heuristic reader produced before merging) for audits."""
    sh = repo.get_sheet(job_id, sheet_id)
    if sh is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sheet not found")
    return {"sheet_id": sh.id, "file_name": sh.file_name, "page_no": sh.page_no, "layout": sh.layout,
            "classification": sh.classification.model_dump(),
            "structural": sh.extraction.model_dump() if sh.extraction else None,
            "fitout": sh.fitout_extraction.model_dump() if sh.fitout_extraction else None,
            "processing_notes": sh.processing_notes}


@app.get("/api/v1/jobs/{job_id}/sheets/{sheet_id}/preview")
def get_preview(job_id: str, sheet_id: str, size: str = Query("thumb", pattern="^(thumb|full)$"),
                _: UserProfile = Depends(auth.current_user)):
    """`size=thumb` (default) is the 1600 px image; `size=full` is the full-resolution render when the
    job has one (falls back to the thumb for jobs processed before full renders were kept)."""
    sh = repo.get_sheet(job_id, sheet_id)
    if sh is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Preview not available")
    stg = get_storage()
    local = None
    if size == "full" and sh.preview_full_path:
        local = stg.resolve(sh.preview_full_path)
    if local is None:
        local = stg.resolve(sh.preview_path)
    if local is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Preview not available")
    return FileResponse(str(local), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


def _recalc_and_save(job: JobRecord, user: UserProfile, what: str) -> JobRecord:
    recalculate(job)
    if job.status == JobStatus.approved:
        job.status = JobStatus.ready  # edits need re-approval
        job.approved_by, job.approved_at = None, None
        _event(job, JobStatus.ready, f"Approval cleared: {what} by {user.email}")
    elif job.status == JobStatus.failed:
        job.status = JobStatus.ready
        job.error = None
    return repo.save_job(job)


def _stamp(obj, user: UserProfile) -> None:
    obj.confidence = 1.0
    tag = f"edited by {user.email} on {datetime.utcnow():%d-%b-%Y %H:%M} UTC"
    obj.evidence = [e for e in obj.evidence if not e.startswith("edited by")] + [tag]


# members (structural)
@app.post("/api/v1/jobs/{job_id}/members", response_model=JobRecord)
def add_member(job_id: str, member: Dict[str, Any], user: UserProfile = Depends(auth.current_user)) -> JobRecord:
    job = _load_job(job_id)
    _require_editable(job)
    if job.module != Module.structural:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Members belong to structural jobs; use items for fit-out")
    try:
        m = _member_adapter.validate_python({**member, "id": member.get("id") or new_id()})
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, _first_error(exc))
    if any(x.id == m.id for x in job.members):
        raise HTTPException(status.HTTP_409_CONFLICT, "Member id already exists")
    _stamp(m, user)
    m.evidence.insert(0, "added manually")
    job.members.append(m)
    db.audit("member.add", user.email, job.id, f"{m.kind} {m.tag}")
    return _recalc_and_save(job, user, f"member {m.tag} added")


@app.patch("/api/v1/jobs/{job_id}/members/{member_id}", response_model=JobRecord)
def patch_member(job_id: str, member_id: str, upd: MemberUpdate, user: UserProfile = Depends(auth.current_user)) -> JobRecord:
    job = _load_job(job_id)
    _require_editable(job)
    for i, m in enumerate(job.members):
        if m.id == member_id:
            data = m.model_dump()
            data.update({k: v for k, v in upd.member.items() if k not in ("id",)})
            try:
                nm = _member_adapter.validate_python(data)
            except ValidationError as exc:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, _first_error(exc))
            _stamp(nm, user)
            job.members[i] = nm
            db.audit("member.edit", user.email, job.id, f"{nm.kind} {nm.tag}: {sorted(upd.member)}")
            return _recalc_and_save(job, user, f"member {nm.tag} edited")
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")


@app.delete("/api/v1/jobs/{job_id}/members/{member_id}", response_model=JobRecord)
def delete_member(job_id: str, member_id: str, user: UserProfile = Depends(auth.current_user)) -> JobRecord:
    job = _load_job(job_id)
    _require_editable(job)
    before = len(job.members)
    gone = [m.tag for m in job.members if m.id == member_id]
    job.members = [m for m in job.members if m.id != member_id]
    if len(job.members) == before:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    db.audit("member.delete", user.email, job.id, gone[0] if gone else member_id)
    return _recalc_and_save(job, user, f"member {gone[0] if gone else ''} deleted")


# items (fit-out)
@app.post("/api/v1/jobs/{job_id}/items", response_model=JobRecord)
def add_item(job_id: str, item: FitoutItem, user: UserProfile = Depends(auth.current_user)) -> JobRecord:
    job = _load_job(job_id)
    _require_editable(job)
    if job.module != Module.fitout:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Items belong to fit-out jobs; use members for structural")
    if any(x.id == item.id for x in job.fitout_items):
        item.id = new_id()
    item.qty_basis = "manual"
    _stamp(item, user)
    item.evidence.insert(0, "added manually")
    job.fitout_items.append(item)
    db.audit("item.add", user.email, job.id, f"{item.code or item.description[:40]}")
    return _recalc_and_save(job, user, f"item {item.code or item.description[:30]} added")


@app.patch("/api/v1/jobs/{job_id}/items/{item_id}", response_model=JobRecord)
def patch_item(job_id: str, item_id: str, upd: ItemUpdate, user: UserProfile = Depends(auth.current_user)) -> JobRecord:
    job = _load_job(job_id)
    _require_editable(job)
    for i, it in enumerate(job.fitout_items):
        if it.id == item_id:
            data = it.model_dump()
            changes = {k: v for k, v in upd.item.items() if k != "id"}
            data.update(changes)
            try:
                ni = FitoutItem.model_validate(data)
            except ValidationError as exc:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, _first_error(exc))
            if ("qty" in changes or "unit" in changes) and "qty_basis" not in changes:
                ni.qty_basis = "manual"
            _stamp(ni, user)
            job.fitout_items[i] = ni
            db.audit("item.edit", user.email, job.id, f"{ni.code or ni.description[:40]}: {sorted(changes)}")
            return _recalc_and_save(job, user, f"item {ni.code or ''} edited")
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")


@app.delete("/api/v1/jobs/{job_id}/items/{item_id}", response_model=JobRecord)
def delete_item(job_id: str, item_id: str, user: UserProfile = Depends(auth.current_user)) -> JobRecord:
    job = _load_job(job_id)
    _require_editable(job)
    before = len(job.fitout_items)
    gone = [i.code or i.description[:30] for i in job.fitout_items if i.id == item_id]
    job.fitout_items = [i for i in job.fitout_items if i.id != item_id]
    if len(job.fitout_items) == before:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    db.audit("item.delete", user.email, job.id, gone[0] if gone else item_id)
    return _recalc_and_save(job, user, f"item {gone[0] if gone else ''} deleted")


@app.put("/api/v1/jobs/{job_id}/elements", response_model=JobRecord)
def put_elements(job_id: str, body: ElementsUpdate = Body(...), user: UserProfile = Depends(auth.current_user)) -> JobRecord:
    """Replace the elements read from the drawings (rooms, openings, walls, slabs, members, misc items)
    after the reviewer edited them; the measurement sheet, BOQ and materials are recomputed."""
    job = _load_job(job_id)
    _require_editable(job)
    if job.module != Module.measurement:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Elements belong to measurement jobs")
    ex = body.elements
    for lst in (ex.rooms, ex.openings, ex.walls, ex.slabs, ex.members, ex.misc):
        for e in lst:
            if e.confidence < 1.0 and not any(v.startswith("edited by") for v in e.evidence):
                continue
    job.elements = ex
    db.audit("elements.update", user.email, job.id, f"{ex.count()} elements")
    return _recalc_and_save(job, user, "elements edited")


class RecalcRequest(BaseModel):
    standards: Optional[Standards] = None
    currency: Optional[str] = Field(None, max_length=4)


@app.post("/api/v1/jobs/{job_id}/recalculate", response_model=JobRecord)
def recalc(job_id: str, body: Optional[RecalcRequest] = None, user: UserProfile = Depends(auth.current_user)) -> JobRecord:
    job = _load_job(job_id)
    _require_editable(job)
    body = body or RecalcRequest()
    if body.standards is not None:
        job.standards = body.standards
    if body.currency:
        job.currency = body.currency.upper()
    db.audit("job.recalculate", user.email, job.id)
    return _recalc_and_save(job, user, "recalculated")


@app.post("/api/v1/jobs/{job_id}/reprocess", response_model=JobRecord)
def reprocess(job_id: str, user: UserProfile = Depends(auth.current_user)) -> JobRecord:
    job = _load_job(job_id)
    _require_editable(job)
    job.status, job.progress, job.error = JobStatus.queued, 0, None
    job.members, job.result, job.fitout_items, job.rooms, job.boq = [], None, [], [], None
    job.approved_by, job.approved_at, job.export_path = None, None, None
    _event(job, JobStatus.queued, f"Reprocess requested by {user.email}", 0)
    repo.save_job(job)
    db.audit("job.reprocess", user.email, job.id)
    Pipeline.get().submit(job.id)
    return job


@app.post("/api/v1/jobs/{job_id}/approve", response_model=JobRecord)
def approve(job_id: str, user: UserProfile = Depends(auth.require_role("reviewer"))) -> JobRecord:
    job = _load_job(job_id)
    if job.status != JobStatus.ready:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only jobs in 'ready' state can be approved")
    if job.module == Module.structural and not job.members:
        raise HTTPException(status.HTTP_409_CONFLICT, "Nothing to approve: the job has no members")
    if job.module == Module.fitout and not job.fitout_items:
        raise HTTPException(status.HTTP_409_CONFLICT, "Nothing to approve: the job has no BOQ items")
    job.status = JobStatus.approved
    job.approved_by, job.approved_at = user.email, datetime.utcnow()
    _event(job, JobStatus.approved, f"Approved by {user.email}", 100)
    db.audit("job.approve", user.email, job.id)
    return repo.save_job(job)


class RejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


@app.post("/api/v1/jobs/{job_id}/reject", response_model=JobRecord)
def reject(job_id: str, body: RejectRequest, user: UserProfile = Depends(auth.require_role("reviewer"))) -> JobRecord:
    """Send a job back for rework (clears approval if any) with a reason in the timeline."""
    job = _load_job(job_id)
    if job.status not in (JobStatus.ready, JobStatus.approved):
        raise HTTPException(status.HTTP_409_CONFLICT, "Only ready or approved jobs can be sent back")
    job.status = JobStatus.ready
    job.approved_by, job.approved_at, job.export_path = None, None, None
    _event(job, JobStatus.ready, f"Sent back by {user.email}: {body.reason.strip()}", 100)
    db.audit("job.reject", user.email, job.id, body.reason.strip())
    return repo.save_job(job)


@app.get("/api/v1/jobs/{job_id}/export.xlsx")
def export_xlsx(job_id: str, user: UserProfile = Depends(auth.current_user)):
    job = _load_job(job_id)
    if job.status not in (JobStatus.ready, JobStatus.approved):
        raise HTTPException(status.HTTP_409_CONFLICT, "Export is available once the job is ready")
    from app.export import write_workbook
    s = get_settings()
    storage = get_storage()
    local = storage.resolve(job.export_path)
    if local is None:
        job.export_version += 1
        out = s.data_dir / "exports" / f"{job.id}-v{job.export_version}.xlsx"
        out.parent.mkdir(parents=True, exist_ok=True)
        write_workbook(job, out)
        job.export_path = storage.store(out, "exports", f"{job.id}/v{job.export_version}.xlsx")
        repo.save_job(job)
        db.audit("job.export", user.email, job.id, f"v{job.export_version}")
        local = out

    def _slug(t: str) -> str:
        return "".join(ch if ch.isalnum() else "-" for ch in t).strip("-")[:40] or "x"
    kind = "BBS" if job.module == Module.structural else "BOQ"
    fname = f"{_slug(job.project_name)}-{_slug(job.level)}-{kind}-v{job.export_version}.xlsx"
    return FileResponse(str(local), filename=fname,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.delete("/api/v1/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: str, user: UserProfile = Depends(auth.current_user)) -> Response:
    job = _load_job(job_id)
    if user.role != "admin" and job.created_by != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner or an admin can delete a job")
    if job.status in IN_FLIGHT:
        raise HTTPException(status.HTTP_409_CONFLICT, "Wait until processing finishes before deleting")
    s = get_settings()
    for sub in ("uploads", "work", "previews", "cache"):
        shutil.rmtree(s.data_dir / sub / job.id, ignore_errors=True)
    for f in (s.data_dir / "exports").glob(f"{job.id}-v*.xlsx"):
        f.unlink(missing_ok=True)
    for kind in ("uploads", "previews", "exports"):
        try:
            get_storage().delete_prefix(kind, job.id)
        except Exception as exc:  # noqa: BLE001
            log.warning("remote delete failed for %s/%s: %s", kind, job.id, exc)
    repo.delete_job(job.id)
    db.audit("job.delete", user.email, job.id, job.project_name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----------------------------------------------------------------------------- standards
@app.get("/api/v1/standards", response_model=Standards)
def get_standards(_: UserProfile = Depends(auth.current_user)) -> Standards:
    return repo.get_standards()


@app.put("/api/v1/standards", response_model=Standards)
def put_standards(std: Standards, user: UserProfile = Depends(auth.require_role("admin"))) -> Standards:
    if std.ld_factor <= 0 or std.bend_deduction_d < 0 or not std.unit_weight_kg_per_m:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ld, bend deduction and unit weights must be positive")
    db.audit("standards.update", user.email)
    return repo.put_standards(std)


# ----------------------------------------------------------------------------- admin
@app.get("/api/v1/admin/users", response_model=List[UserProfile])
def admin_users(_: UserProfile = Depends(auth.require_role("admin"))) -> List[UserProfile]:
    return repo.list_users()


@app.post("/api/v1/admin/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
def admin_invite(req: InviteRequest, admin: UserProfile = Depends(auth.require_role("admin"))) -> InviteResponse:
    out = auth.invite(req)
    db.audit("user.invite", admin.email, out.profile.id, f"{out.profile.email} as {out.profile.role}")
    return out


@app.patch("/api/v1/admin/users/{user_id}", response_model=UserProfile)
def admin_update_user(user_id: str, upd: RoleUpdate, admin: UserProfile = Depends(auth.require_role("admin"))) -> UserProfile:
    if user_id == admin.id and upd.role not in (None, "admin"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot remove your own admin role")
    if user_id == admin.id and upd.is_active is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate yourself")
    fields = {k: v for k, v in upd.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nothing to update")
    user = repo.update_user(user_id, **fields)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    db.audit("user.update", admin.email, user_id, str(fields))
    return user


@app.post("/api/v1/admin/users/{user_id}/reset-password", response_model=InviteResponse)
def admin_reset_password(user_id: str, admin: UserProfile = Depends(auth.require_role("admin"))) -> InviteResponse:
    """Issue a new temporary password (shown once); the user must change it at next login."""
    user = repo.get_user(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    temp = auth.generate_temp_password()
    repo.update_user(user_id, password_hash=auth.hash_password(temp), must_set_password=True)
    db.audit("user.reset_password", admin.email, user_id, user.email)
    return InviteResponse(profile=repo.get_user(user_id), temporary_password=temp)  # type: ignore[arg-type]


@app.delete("/api/v1/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_user(user_id: str, admin: UserProfile = Depends(auth.require_role("admin"))) -> Response:
    if user_id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot delete yourself")
    victim = repo.get_user(user_id)
    if victim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    repo.delete_user(user_id)
    db.audit("user.delete", admin.email, user_id, victim.email)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/v1/admin/audit")
def admin_audit(limit: int = Query(100, ge=1, le=500), _: UserProfile = Depends(auth.require_role("admin"))) -> Dict[str, Any]:
    return {"items": db.recent_audit(limit)}


@app.get("/api/v1/admin/backup")
def admin_backup(admin: UserProfile = Depends(auth.require_role("admin"))):
    """Consistent SQLite snapshot (online backup API) as a download."""
    out = Path(tempfile.mkdtemp(prefix="boqbackup_")) / f"avighna-boq-{datetime.utcnow():%Y%m%d-%H%M%S}.db"
    out = db.export_snapshot(out)   # .db for SQLite, .json dump for Postgres
    db.audit("db.backup", admin.email)
    media = "application/vnd.sqlite3" if out.suffix == ".db" else "application/json"
    return FileResponse(str(out), filename=out.name, media_type=media)


def _first_error(exc: ValidationError) -> str:
    e = exc.errors()[0]
    loc = ".".join(str(x) for x in e.get("loc", []))
    return f"{loc}: {e.get('msg', 'invalid value')}" if loc else e.get("msg", "invalid value")
