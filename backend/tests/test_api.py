"""API integration tests: auth, standards, fit-out job on a vector PDF, structural job on a synthetic sheet."""
from __future__ import annotations

import time
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from app.main import app

REF_PDF = Path("/Users/shubhammishra/Downloads/20250930 Detail Design Submission R1/Drawing Package/pdf/Avighna Group Office_100� DD Issue.pdf")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def admin_token(client):
    r = client.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "Test-Admin-123"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["profile"]["must_set_password"] is True
    tok = body["access_token"]
    r = client.post("/api/v1/auth/set-password", json={"password": "New-Admin-Pass-1"},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200 and r.json()["must_set_password"] is False
    r = client.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "New-Admin-Pass-1"})
    return r.json()["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _wait(client, tok, job_id, timeout=240):
    t0 = time.time()
    while time.time() - t0 < timeout:
        job = client.get(f"/api/v1/jobs/{job_id}", headers=_h(tok)).json()
        if job["status"] in ("ready", "failed"):
            return job
        time.sleep(1.0)
    raise AssertionError("job did not finish in time")


def test_health_and_auth_errors(client):
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/api/v1/me").status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "nobody@x", "password": "x"}).status_code == 401


def test_users_and_roles(client, admin_token):
    r = client.post("/api/v1/admin/invite", json={"email": "eng@test.local", "full_name": "Eng", "role": "engineer"},
                    headers=_h(admin_token))
    assert r.status_code == 201, r.text
    temp = r.json()["temporary_password"]
    r = client.post("/api/v1/auth/login", json={"email": "eng@test.local", "password": temp})
    eng = r.json()["access_token"]
    assert client.get("/api/v1/admin/users", headers=_h(eng)).status_code == 403
    assert client.put("/api/v1/standards", json={}, headers=_h(eng)).status_code == 403
    r = client.patch(f"/api/v1/admin/users/{r.json()['profile']['id']}", json={"role": "reviewer"}, headers=_h(admin_token))
    assert r.json()["role"] == "reviewer"
    assert len(client.get("/api/v1/admin/users", headers=_h(admin_token)).json()) == 2


def test_standards_roundtrip(client, admin_token):
    std = client.get("/api/v1/standards", headers=_h(admin_token)).json()
    assert std["ld_factor"] == 39 and std["unit_weight_kg_per_m"]["20"] == 2.47
    std["cover_beam_mm"] = 35
    r = client.put("/api/v1/standards", json=std, headers=_h(admin_token))
    assert r.status_code == 200 and r.json()["cover_beam_mm"] == 35
    std["cover_beam_mm"] = 30
    client.put("/api/v1/standards", json=std, headers=_h(admin_token))


def test_structural_job_synthetic(client, admin_token, tmp_path):
    # a synthetic 'beam schedule' sheet the heuristic reader can parse without AI
    doc = fitz.open()
    page = doc.new_page(width=1190, height=842)
    y = 80
    page.insert_text((60, 40), "BEAM SCHEDULE - 14TH FLOOR   SCALE 1:50   DWG NO 9680/P.P/13", fontsize=16)
    for line in ["B1   230x450   2-T16   2-T12   T8@150 c/c", "B2 (2 nos)   230x600   3-T20   2-T16   T8@100 c/c",
                 "C1   300x600   8-T16   T8@100 c/c"]:
        page.insert_text((60, y), line, fontsize=14); y += 30
    pdf = tmp_path / "beam_schedule.pdf"
    doc.save(str(pdf)); doc.close()
    with open(pdf, "rb") as fh:
        r = client.post("/api/v1/jobs", data={"module": "structural", "project_name": "Nishika Elysium (Avighna)",
                                              "level": "14th Floor", "contractor": "Mehta Jaising Builders LLP"},
                        files=[("files", ("beam_schedule.pdf", fh, "application/pdf"))], headers=_h(admin_token))
    assert r.status_code == 202, r.text
    job = _wait(client, admin_token, r.json()["job_id"])
    assert job["status"] == "ready", job.get("error")
    assert job["module"] == "structural" and job["sheet_count"] == 1
    tags = sorted(m["tag"] for m in job["members"])
    assert tags == ["B1", "B2", "C1"], tags
    assert job["result"]["summary"]["grand_total_t"] > 0
    b1 = next(m for m in job["members"] if m["tag"] == "B1")
    # reviewer edits the span -> recalculated
    r = client.patch(f"/api/v1/jobs/{job['id']}/members/{b1['id']}", json={"member": {"span_m": 4.5}}, headers=_h(admin_token))
    assert r.status_code == 200
    nb1 = next(m for m in r.json()["members"] if m["tag"] == "B1")
    assert nb1["span_m"] == 4.5 and nb1["confidence"] == 1.0
    assert r.json()["result"]["summary"]["grand_total_t"] > job["result"]["summary"]["grand_total_t"]
    # add + delete
    r = client.post(f"/api/v1/jobs/{job['id']}/members", json={"kind": "wall", "tag": "W1", "length_m": 3, "thickness_m": 0.15,
                    "height_m": 3, "vertical": {"dia_mm": 8, "spacing_mm": 150}, "horizontal": {"dia_mm": 8, "spacing_mm": 200}},
                    headers=_h(admin_token))
    assert r.status_code == 200 and any(m["tag"] == "W1" for m in r.json()["members"])
    wid = next(m["id"] for m in r.json()["members"] if m["tag"] == "W1")
    assert client.delete(f"/api/v1/jobs/{job['id']}/members/{wid}", headers=_h(admin_token)).status_code == 200
    # approve + export
    r = client.post(f"/api/v1/jobs/{job['id']}/approve", headers=_h(admin_token))
    assert r.status_code == 200 and r.json()["status"] == "approved"
    r = client.get(f"/api/v1/jobs/{job['id']}/export.xlsx", headers=_h(admin_token))
    assert r.status_code in (200, 501), r.text
    if r.status_code == 200:
        assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
        assert len(r.content) > 5000
    sheets = client.get(f"/api/v1/jobs/{job['id']}/sheets", headers=_h(admin_token)).json()
    assert len(sheets) == 1 and sheets[0]["classification"]["discipline"] == "structural"
    pv = client.get(f"/api/v1/jobs/{job['id']}/sheets/{sheets[0]['id']}/preview", headers=_h(admin_token))
    assert pv.status_code == 200 and pv.headers["content-type"] == "image/png"


@pytest.mark.skipif(not REF_PDF.exists(), reason="reference PDF not on this machine")
def test_fitout_job_pdf(client, admin_token, tmp_path):
    src = fitz.open(str(REF_PDF))
    doc = fitz.open()
    doc.insert_pdf(src, from_page=9, to_page=11)  # floor finishes, wall finishes, RCP
    pdf = tmp_path / "finishes.pdf"
    doc.save(str(pdf)); doc.close(); src.close()
    with open(pdf, "rb") as fh:
        r = client.post("/api/v1/jobs", data={"module": "fitout", "project_name": "Avighna Group Office", "level": "Sales Center",
                                              "location": "Dubai", "currency": "AED"},
                        files=[("files", ("finishes.pdf", fh, "application/pdf"))], headers=_h(admin_token))
    assert r.status_code == 202, r.text
    job = _wait(client, admin_token, r.json()["job_id"])
    assert job["status"] == "ready", job.get("error")
    assert job["sheet_count"] == 3 and job["boq"] is not None
    sheets = client.get(f"/api/v1/jobs/{job['id']}/sheets", headers=_h(admin_token)).json()
    types = [s["classification"]["sheet_type"] for s in sheets]
    assert "floor_finishes_plan" in types and "ceiling_plan" in types
    assert all(s["classification"]["relevant_for_boq"] for s in sheets)
    # add an item manually and check the BOQ recomputes with amount
    r = client.post(f"/api/v1/jobs/{job['id']}/items", json={"division": "finishes", "section": "Floor Finishes", "code": "FC-201",
                    "description": "Cream Cremo Delicato stone", "unit": "m2", "qty": 270, "rate": 350}, headers=_h(admin_token))
    assert r.status_code == 200
    boq = r.json()["boq"]
    line = next(l for s in boq["sections"] for l in s["lines"] if l["code"] == "FC-201")
    assert line["amount"] == 94500 and boq["summary"]["currency"] == "AED"
    lst = client.get("/api/v1/jobs?module=fitout", headers=_h(admin_token)).json()
    assert lst["total"] >= 1 and lst["items"][0]["headline"]
    assert client.get("/api/v1/stats", headers=_h(admin_token)).json()["jobs_total"] >= 2
