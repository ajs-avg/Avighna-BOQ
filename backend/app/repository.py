"""Repository: typed access to jobs, sheets, users and standards on top of app.db."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app import db
from app.config import get_settings
from app.models.schemas import (
    JobRecord, JobStatus, JobSummaryRecord, Module, SheetRecord, Standards, UserProfile,
)


# ----------------------------------------------------------------------------- jobs
def _headline(job: JobRecord) -> Tuple[int, Optional[float], Optional[float], str]:
    if job.module == Module.structural:
        n = len(job.members)
        tons = job.result.summary.grand_total_t if job.result else None
        head = f"{tons:,.2f} t steel" if tons is not None else (f"{n} members" if n else "")
        return n, tons, None, head
    n = len(job.fitout_items)
    amount = job.boq.summary.grand_total if (job.boq and job.boq.summary.priced_lines) else None
    parts = []
    if job.boq:
        q = job.boq.summary.qty_by_unit
        if q.get("m2"):
            parts.append(f"{q['m2']:,.0f} m²")
        if q.get("lm"):
            parts.append(f"{q['lm']:,.0f} lm")
        if q.get("nos"):
            parts.append(f"{q['nos']:,.0f} nos")
    head = f"{n} items" + (" · " + " · ".join(parts) if parts else "")
    if amount:
        head += f" · {job.currency} {amount:,.0f}"
    return n, None, amount, head if n else ""


def save_job(job: JobRecord) -> JobRecord:
    job.updated_at = datetime.utcnow()
    doc = job.model_dump_json()
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO jobs(id, module, status, project_name, level, created_by, created_at, updated_at, doc) "
            "VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET module=excluded.module, status=excluded.status, "
            "project_name=excluded.project_name, level=excluded.level, updated_at=excluded.updated_at, doc=excluded.doc",
            (job.id, job.module.value, job.status.value, job.project_name, job.level, job.created_by,
             job.created_at.isoformat(), job.updated_at.isoformat(), doc),
        )
    return job


def get_job(job_id: str) -> Optional[JobRecord]:
    row = db.query_one("SELECT doc FROM jobs WHERE id=?", (job_id,))
    return JobRecord.model_validate_json(row["doc"]) if row else None


def delete_job(job_id: str) -> None:
    with db.tx() as conn:
        conn.execute("DELETE FROM sheets WHERE job_id=?", (job_id,))
        conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))


def list_jobs(limit: int = 50, offset: int = 0, module: Optional[str] = None,
              status: Optional[str] = None) -> Tuple[List[JobSummaryRecord], int]:
    where, params = [], []  # type: ignore[var-annotated]
    if module:
        where.append("module=?"); params.append(module)
    if status:
        where.append("status=?"); params.append(status)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    total = db.query_one(f"SELECT COUNT(*) AS n FROM jobs{clause}", tuple(params))["n"]
    rows = db.query(f"SELECT doc FROM jobs{clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    tuple(params) + (limit, offset))
    out: List[JobSummaryRecord] = []
    for r in rows:
        job = JobRecord.model_validate_json(r["doc"])
        n, tons, amount, head = _headline(job)
        out.append(JobSummaryRecord(
            id=job.id, module=job.module, project_name=job.project_name, level=job.level,
            status=job.status, progress=job.progress, created_at=job.created_at, updated_at=job.updated_at,
            created_by_email=job.created_by_email, member_count=n, grand_total_t=tons,
            grand_total_amount=amount, headline=head, file_names=[f.name for f in job.source_files],
        ))
    return out, int(total)


def job_stats() -> Dict[str, Any]:
    rows = db.query("SELECT doc FROM jobs ORDER BY created_at DESC LIMIT 500")
    month = datetime.utcnow().strftime("%Y-%m")
    stats = {"jobs_total": 0, "jobs_this_month": 0, "steel_t": 0.0, "boq_lines": 0,
             "awaiting_review": 0, "approved": 0, "failed": 0}
    for r in rows:
        job = JobRecord.model_validate_json(r["doc"])
        stats["jobs_total"] += 1
        if job.created_at.strftime("%Y-%m") == month:
            stats["jobs_this_month"] += 1
        if job.status == JobStatus.ready:
            stats["awaiting_review"] += 1
        elif job.status == JobStatus.approved:
            stats["approved"] += 1
        elif job.status == JobStatus.failed:
            stats["failed"] += 1
        if job.result:
            stats["steel_t"] += job.result.summary.grand_total_t
        if job.boq:
            stats["boq_lines"] += job.boq.summary.line_count
    stats["steel_t"] = round(stats["steel_t"], 3)
    return stats


# ----------------------------------------------------------------------------- sheets
def save_sheets(job_id: str, sheets: List[SheetRecord]) -> None:
    with db.tx() as conn:
        conn.execute("DELETE FROM sheets WHERE job_id=?", (job_id,))
        for i, s in enumerate(sheets):
            conn.execute("INSERT INTO sheets(id, job_id, seq, doc) VALUES(?,?,?,?)",
                         (s.id, job_id, i, s.model_dump_json()))


def get_sheets(job_id: str) -> List[SheetRecord]:
    rows = db.query("SELECT doc FROM sheets WHERE job_id=? ORDER BY seq", (job_id,))
    return [SheetRecord.model_validate_json(r["doc"]) for r in rows]


def get_sheet(job_id: str, sheet_id: str) -> Optional[SheetRecord]:
    row = db.query_one("SELECT doc FROM sheets WHERE job_id=? AND id=?", (job_id, sheet_id))
    return SheetRecord.model_validate_json(row["doc"]) if row else None


# ----------------------------------------------------------------------------- standards
def get_standards() -> Standards:
    doc = db.get_setting("standards")
    if doc:
        return Standards.model_validate(doc)
    seed = get_settings().database_dir / "seed" / "standards.default.json"
    if seed.exists():
        try:
            return Standards.model_validate(json.loads(seed.read_text()))
        except Exception:
            pass
    return Standards()


def put_standards(std: Standards) -> Standards:
    db.put_setting("standards", json.loads(std.model_dump_json()))
    return std


# ----------------------------------------------------------------------------- users
def _row_to_profile(row) -> UserProfile:
    return UserProfile(
        id=row["id"], email=row["email"], full_name=row["full_name"], role=row["role"],
        must_set_password=bool(row["must_set_password"]), is_active=bool(row["is_active"]),
        created_at=datetime.fromisoformat(row["created_at"].rstrip("Z")) if row["created_at"] else None,
        last_sign_in_at=datetime.fromisoformat(row["last_sign_in_at"].rstrip("Z")) if row["last_sign_in_at"] else None,
    )


def list_users() -> List[UserProfile]:
    return [_row_to_profile(r) for r in db.query("SELECT * FROM users ORDER BY created_at")]


def get_user(user_id: str) -> Optional[UserProfile]:
    row = db.query_one("SELECT * FROM users WHERE id=?", (user_id,))
    return _row_to_profile(row) if row else None


def get_user_row_by_email(email: str):
    return db.query_one("SELECT * FROM users WHERE email=?", (email.strip().lower(),))


def count_users() -> int:
    return int(db.query_one("SELECT COUNT(*) AS n FROM users")["n"])


def create_user(user_id: str, email: str, full_name: Optional[str], role: str, password_hash: str,
                must_set_password: bool) -> UserProfile:
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO users(id, email, full_name, role, password_hash, must_set_password, is_active, created_at) "
            "VALUES(?,?,?,?,?,?,1,?)",
            (user_id, email.strip().lower(), full_name, role, password_hash, 1 if must_set_password else 0, db.now_iso()),
        )
    return get_user(user_id)  # type: ignore[return-value]


def update_user(user_id: str, **fields: Any) -> Optional[UserProfile]:
    allowed = {"full_name", "role", "password_hash", "must_set_password", "is_active", "last_sign_in_at"}
    sets, params = [], []  # type: ignore[var-annotated]
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k}=?")
            params.append(int(v) if isinstance(v, bool) else v)
    if sets:
        with db.tx() as conn:
            conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", tuple(params) + (user_id,))
    return get_user(user_id)


def delete_user(user_id: str) -> None:
    db.execute("DELETE FROM users WHERE id=?", (user_id,))
