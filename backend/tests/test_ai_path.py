"""Exercise the Gemini branch of the pipeline with a fake client (no network, no key):
classification -> structural extraction -> BBS, and classification -> fit-out extraction -> BOQ."""
from __future__ import annotations

import time

import fitz
import pytest
from fastapi.testclient import TestClient

from app.ai import gemini as gm
from app.ai.prompts import (
    AIBarGroup, AIBeam, AIColumn, AIFitoutExtraction, AIFitoutItem, AILegendEntry, AIRoom, AISheetClass,
    AISlab, AISlabLayer, AIStirrup, AIStructuralExtraction, AITie, AIGeneralNotes,
)
from app.main import app


class FakeGemini:
    enabled = True
    model_fast = "fake-flash"
    model_pro = "fake-pro"
    message = "fake"
    calls: list = []

    def status(self):
        from app.models.schemas import AIStatus
        return AIStatus(enabled=True, provider="gemini", model_fast=self.model_fast, model_pro=self.model_pro, message=self.message)

    def generate_json(self, schema, prompt, images=(), tier="pro", **kw):
        self.calls.append((schema.__name__, tier, len(images), len(prompt)))
        assert images and isinstance(images[0], (bytes, bytearray))
        if schema is AISheetClass:
            structural = "BEAM" in prompt.upper() and "SCHEDULE" in prompt.upper()
            return AISheetClass(sheet_type="beam_schedule" if structural else "floor_finishes_plan",
                                discipline="structural" if structural else "interior", drawing_number="X-01",
                                title="t", level="14th Floor", scale="1:50", units="mm", relevant_for_bbs=structural,
                                relevant_for_boq=not structural, confidence=0.9, summary="fake")
        if schema is AIStructuralExtraction:
            return AIStructuralExtraction(
                beams=[AIBeam(tag="B1A", nos=1, span_mm=2450, width_mm=230, depth_mm=750,
                              bottom_bars=[AIBarGroup(count=2, dia_mm=20)], top_bars=[AIBarGroup(count=2, dia_mm=20)],
                              sfr_bars=[AIBarGroup(count=2, dia_mm=8)],
                              stirrups=[AIStirrup(dia_mm=8, spacing_mm=100, zone="end"), AIStirrup(dia_mm=8, spacing_mm=150, zone="mid")],
                              confidence=0.92, evidence=["B1A 230x750", "2-T20"])],
                slabs=[AISlab(tag="S3", short_span_mm=4900, long_span_mm=5350, thickness_mm=175,
                              short_main=AISlabLayer(dia_mm=8, spacing_mm=150, bent_up=True),
                              long_main=AISlabLayer(dia_mm=8, spacing_mm=175, bent_up=True), confidence=0.8)],
                columns=[AIColumn(tag="C1", nos=2, length_mm=300, width_mm=600, height_mm=3800,
                                  vertical_bars=[AIBarGroup(count=8, dia_mm=16)], ties=[AITie(dia_mm=8, spacing_mm=100)], confidence=0.85)],
                general_notes=AIGeneralNotes(ld_factor=39, cover_beam_mm=30, cover_slab_mm=20, cover_column_mm=40, concrete_grade="M40"),
            )
        if schema is AIFitoutExtraction:
            return AIFitoutExtraction(
                items=[AIFitoutItem(division="finishes", section="Floor Finishes", code="FC-201", description="Cream Cremo Delicato stone",
                                    unit="m2", qty=270, qty_basis="measured", rooms=["SALES AREA"], confidence=0.9, evidence=["FC-201"]),
                       AIFitoutItem(division="lighting", section="Lighting", code="LI-501", description="Pendant light", unit="nos", qty=3,
                                    qty_basis="counted", confidence=0.8)],
                rooms=[AIRoom(name="SALES AREA", area_m2=243.5, floor_finish="FC-201", confidence=0.9)],
                legend=[AILegendEntry(code="FC-201", description="Cream Cremo Delicato 1200x1200 stone")],
            )
        raise AssertionError(f"unexpected schema {schema}")


@pytest.fixture(scope="module")
def fake(monkeypatch_module):
    f = FakeGemini()
    monkeypatch_module.setattr(gm.GeminiClient, "get", classmethod(lambda cls: f))
    return f


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="module")
def client(fake):
    with TestClient(app) as c:
        yield c


def _token(client):
    r = client.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "Test-Admin-123"})
    if r.status_code != 200:  # password was changed by test_api when run together
        r = client.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "New-Admin-Pass-1"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _pdf(tmp_path, title):
    doc = fitz.open(); page = doc.new_page(width=1190, height=842)
    page.insert_text((60, 60), title, fontsize=18)
    p = tmp_path / "sheet.pdf"; doc.save(str(p)); doc.close()
    return p


def _wait(client, h, jid):
    for _ in range(120):
        j = client.get(f"/api/v1/jobs/{jid}", headers=h).json()
        if j["status"] in ("ready", "failed"):
            return j
        time.sleep(0.5)
    raise AssertionError("timeout")


def test_ai_status_reports_fake_models(client, fake):
    h = _token(client)
    st = client.get("/api/v1/ai/status", headers=h).json()
    assert st["enabled"] and st["model_pro"] == "fake-pro"


def test_structural_job_through_ai(client, fake, tmp_path):
    h = _token(client)
    with open(_pdf(tmp_path, "BEAM SCHEDULE 14TH FLOOR"), "rb") as fh:
        r = client.post("/api/v1/jobs", data={"module": "structural", "project_name": "P", "level": "14th Floor"},
                        files=[("files", ("beams.pdf", fh, "application/pdf"))], headers=h)
    j = _wait(client, h, r.json()["job_id"])
    assert j["status"] == "ready", j.get("error")
    assert sorted(m["tag"] for m in j["members"]) == ["B1A", "C1", "S3"]
    assert j["standards"]["ld_factor"] == 39 and j["general_notes"]["concrete_grade"] == "M40"
    b1a = next(m for m in j["result"]["members"] if m["tag"] == "B1A")
    assert abs(b1a["weight_kg"] - 63.333) < 0.01     # same numbers as the reference sheet test
    assert j["result"]["summary"]["grand_total_t"] > 0.2
    assert any(c[0] == "AISheetClass" and c[1] == "fast" for c in fake.calls)
    assert any(c[0] == "AIStructuralExtraction" and c[1] == "pro" for c in fake.calls)
    sheets = client.get(f"/api/v1/jobs/{j['id']}/sheets", headers=h).json()
    assert sheets[0]["classification"]["sheet_type"] == "beam_schedule" and sheets[0]["classification"]["confidence"] == 0.9


def test_fitout_job_through_ai(client, fake, tmp_path):
    h = _token(client)
    with open(_pdf(tmp_path, "FLOOR FINISHES PLAN"), "rb") as fh:
        r = client.post("/api/v1/jobs", data={"module": "fitout", "project_name": "P", "level": "GF", "currency": "AED"},
                        files=[("files", ("finishes.pdf", fh, "application/pdf"))], headers=h)
    j = _wait(client, h, r.json()["job_id"])
    assert j["status"] == "ready", j.get("error")
    codes = {i["code"]: i for i in j["fitout_items"]}
    assert codes["FC-201"]["qty"] == 270 and codes["FC-201"]["specification"] == "Cream Cremo Delicato 1200x1200 stone"
    assert j["legend"]["FC-201"].startswith("Cream") and j["rooms"][0]["name"] == "SALES AREA"
    assert j["boq"]["summary"]["qty_by_unit"] == {"m2": 270.0, "nos": 3.0}
    r = client.get(f"/api/v1/jobs/{j['id']}/export.xlsx", headers=h)
    assert r.status_code == 200 and len(r.content) > 5000
