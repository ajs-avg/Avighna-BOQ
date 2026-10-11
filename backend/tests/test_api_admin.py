"""New endpoints: reject flow, system info, audit log, backup, admin password reset, login throttle, validation."""
from __future__ import annotations

import sqlite3

import fitz
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, email, password):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return r


@pytest.fixture(scope="module")
def admin(client):
    r = _login(client, "admin@test.local", "Test-Admin-123")
    if r.status_code != 200:  # earlier test module may have changed it
        r = _login(client, "admin@test.local", "New-Admin-Pass-1")
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _structural_job(client, h, tmp_path):
    doc = fitz.open(); page = doc.new_page(width=1190, height=842)
    page.insert_text((60, 40), "BEAM SCHEDULE 14TH FLOOR", fontsize=16)
    page.insert_text((60, 80), "B1   230x450   3000   2-T16   2-T12   T8@150 c/c", fontsize=14)
    p = tmp_path / "b.pdf"; doc.save(str(p)); doc.close()
    with open(p, "rb") as fh:
        r = client.post("/api/v1/jobs", data={"module": "structural", "project_name": "P", "level": "L"},
                        files=[("files", ("b.pdf", fh, "application/pdf"))], headers=h)
    assert r.status_code == 202
    jid = r.json()["job_id"]
    import time
    for _ in range(120):
        j = client.get(f"/api/v1/jobs/{jid}", headers=h).json()
        if j["status"] in ("ready", "failed"):
            return j
        time.sleep(0.5)
    raise AssertionError("timeout")


def test_system_and_stats(client, admin):
    s = client.get("/api/v1/system", headers=admin).json()
    assert s["version"] and "converters" in s and "stats" in s and s["users"] >= 1
    assert client.get("/api/v1/system").status_code == 401


def test_reject_flow_and_edit_locks(client, admin, tmp_path):
    job = _structural_job(client, admin, tmp_path)
    assert job["status"] == "ready" and job["members"], job.get("error")
    jid = job["id"]
    # approve then send back with a reason
    assert client.post(f"/api/v1/jobs/{jid}/approve", headers=admin).json()["status"] == "approved"
    r = client.post(f"/api/v1/jobs/{jid}/reject", json={"reason": "B1 span looks wrong"}, headers=admin)
    assert r.status_code == 200 and r.json()["status"] == "ready" and r.json()["approved_by"] is None
    assert any("Sent back" in e["message"] and "span looks wrong" in e["message"] for e in r.json()["events"])
    assert client.post(f"/api/v1/jobs/{jid}/reject", json={"reason": "x"}, headers=admin).status_code == 422
    # editing an approved job clears approval and stamps the editor
    client.post(f"/api/v1/jobs/{jid}/approve", headers=admin)
    mid = job["members"][0]["id"]
    r = client.patch(f"/api/v1/jobs/{jid}/members/{mid}", json={"member": {"nos": 2}}, headers=admin)
    assert r.status_code == 200 and r.json()["status"] == "ready"
    m = next(x for x in r.json()["members"] if x["id"] == mid)
    assert any(e.startswith("edited by admin@test.local") for e in m["evidence"]) and m["confidence"] == 1.0
    # wrong module operations are refused
    assert client.post(f"/api/v1/jobs/{jid}/items", json={"description": "x", "unit": "nos", "qty": 1}, headers=admin).status_code == 400
    # invalid member update -> 422 with a readable message
    r = client.patch(f"/api/v1/jobs/{jid}/members/{mid}", json={"member": {"span_m": -1}}, headers=admin)
    assert r.status_code == 422 and "span_m" in r.json()["detail"]
    # bad list filters
    assert client.get("/api/v1/jobs?module=nope", headers=admin).status_code == 400
    assert client.get("/api/v1/jobs?status=nope", headers=admin).status_code == 400


def test_approve_requires_content(client, admin, tmp_path):
    doc = fitz.open(); doc.new_page(width=600, height=400)
    p = tmp_path / "empty.pdf"; doc.save(str(p)); doc.close()
    with open(p, "rb") as fh:
        r = client.post("/api/v1/jobs", data={"module": "structural", "project_name": "E", "level": "L"},
                        files=[("files", ("empty.pdf", fh, "application/pdf"))], headers=admin)
    jid = r.json()["job_id"]
    import time
    for _ in range(120):
        j = client.get(f"/api/v1/jobs/{jid}", headers=admin).json()
        if j["status"] in ("ready", "failed"):
            break
        time.sleep(0.5)
    assert j["status"] == "ready" and not j["members"]
    assert client.post(f"/api/v1/jobs/{jid}/approve", headers=admin).status_code == 409


def test_admin_reset_password_audit_backup(client, admin, tmp_path):
    r = client.post("/api/v1/admin/invite", json={"email": "rev@test.local", "role": "reviewer"}, headers=admin)
    uid = r.json()["profile"]["id"]
    r = client.post(f"/api/v1/admin/users/{uid}/reset-password", headers=admin)
    assert r.status_code == 200 and r.json()["profile"]["must_set_password"] is True
    temp = r.json()["temporary_password"]
    assert _login(client, "rev@test.local", temp).status_code == 200
    audit = client.get("/api/v1/admin/audit?limit=50", headers=admin).json()["items"]
    actions = {a["action"] for a in audit}
    assert {"login", "user.invite", "user.reset_password", "job.approve", "job.reject"} <= actions
    assert audit[0]["at"] >= audit[-1]["at"]
    r = client.get("/api/v1/admin/backup", headers=admin)
    assert r.status_code == 200
    cd = r.headers["content-disposition"]
    if cd.endswith('.db"'):                      # SQLite: a real database copy
        bk = tmp_path / "bk.db"; bk.write_bytes(r.content)
        con = sqlite3.connect(str(bk))
        assert con.execute("SELECT COUNT(*) FROM users").fetchone()[0] >= 2
        con.close()
    else:                                        # Postgres: JSON dump of every table
        import json as _json
        assert cd.endswith('.json"')
        dump = _json.loads(r.content)
        assert len(dump["users"]) >= 2 and "jobs" in dump and "audit_log" in dump
    # non-admin cannot read the audit log or backup
    rev = _login(client, "rev@test.local", temp).json()["access_token"]
    h = {"Authorization": f"Bearer {rev}"}
    assert client.get("/api/v1/admin/audit", headers=h).status_code == 403
    assert client.get("/api/v1/admin/backup", headers=h).status_code == 403


def test_login_throttle(client):
    for _ in range(8):
        assert _login(client, "nobody@test.local", "wrong").status_code == 401
    assert _login(client, "nobody@test.local", "wrong").status_code == 429
