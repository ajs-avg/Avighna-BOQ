"""Review questions and decisions.

A tiny synthetic plan: beam B1 is drawn 300 mm wide while the beam schedule says 230, and
a slab panel sits on it. The reader must ask about the width (with a picture), ask the
slab-over-beam rule, understand typed answers, apply a confirmed answer, record it, undo
it, and apply it again after the drawing is re-read.
"""
from __future__ import annotations

import time

import ezdxf
import pytest
from fastapi.testclient import TestClient

from app.decisions import QuestionError, apply_answer, interpret_rules, reapply_decisions, undo_decision
from app.engine.measurement import compute_measurement
from app.extract.structural import read_structural_dxf, structural_to_measurement
from app.extract.structural.questions import build_questions
from app.main import app
from app.models.schemas import AnswerRequest, JobRecord


def _text(msp, s, x, y, layer, h=200.0, rot=0.0):
    msp.add_text(s, dxfattribs={"layer": layer, "height": h, "rotation": rot, "insert": (x, y)})


def _col(msp, x0, y0, x1, y1):
    h = msp.add_hatch(dxfattribs={"layer": "column hatch"})
    h.paths.add_polyline_path([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], is_closed=True)


@pytest.fixture()
def plan(tmp_path):
    doc = ezdxf.new("R2018")
    for name in ("BEAM", "BEAM NO.", "BEAM SIZES", "COLUMN SIZE", "S-COLS-NUM", "Text", "SLAB", "column hatch"):
        if name not in doc.layers:
            doc.layers.add(name)
    msp = doc.modelspace()
    cols = [(0, 0, "C1"), (5300, 0, "C2"), (0, 6000, "C3"), (5300, 6000, "C4"), (10000, 0, "C5")]
    for x, y, nm in cols:
        _col(msp, x, y, x + 300, y + 600)
        _text(msp, nm, x + 60, y + 700, "S-COLS-NUM")
        _text(msp, "(300X600)", x + 60, y + 420, "COLUMN SIZE")
    # B1: edge lines 300 apart, but the schedule (and its plan label) say 230
    msp.add_line((0, 150), (5600, 150), dxfattribs={"layer": "BEAM"})
    msp.add_line((0, 450), (5600, 450), dxfattribs={"layer": "BEAM"})
    _text(msp, "B1", 2500, 480, "BEAM NO.")
    _text(msp, "(230X750)", 2500, 40, "BEAM SIZES")
    # slab panel S1 on top of the beam
    for a, b in (((300, 450), (5300, 450)), ((300, 3450), (5300, 3450)), ((300, 450), (300, 3450)), ((5300, 450), (5300, 3450))):
        msp.add_line(a, b, dxfattribs={"layer": "SLAB"})
    _text(msp, "S1", 2800, 2000, "COLUMN SIZE")
    _text(msp, "150 THK", 2800, 1600, "Text")
    _text(msp, "BEAM SCHEDULE: TEST FLOOR", 60000, 1500, "Text")
    for i, (nm, b, d) in enumerate([("B1", "230", "750"), ("B2", "300", "600"), ("B3,B4", "200", "450")]):
        y = -i * 900
        _text(msp, nm, 60000, y, "Text")
        _text(msp, b, 62500, y, "Text")
        _text(msp, d, 64500, y, "Text")
    p = tmp_path / "beam_layout_test.dxf"
    doc.saveas(p)
    return p


def _read(plan):
    res = read_structural_dxf(plan)
    ex = structural_to_measurement(res, "beam_layout_test.dxf [Model]", level="T")
    return res, ex, build_questions(res, ex, "beam_layout_test.dxf [Model]")


def _job(ex, qs) -> JobRecord:
    job = JobRecord(id="t1", project_name="P", level="T", elements=ex)
    job.questions = [q for q, _ in qs]
    return job


def test_questions_are_built_with_pictures(plan):
    _, ex, qs = _read(plan)
    keys = {q.key: (q, png) for q, png in qs}
    assert "beam-width:B1" in keys and "rule:slab-over-beam" in keys
    q, png = keys["beam-width:B1"]
    assert png and png[:8] == b"\x89PNG\r\n\x1a\n"            # a highlighted crop of the drawing
    assert {o.id for o in q.options} == {"schedule", "drawing"}
    assert next(o for o in q.options if o.id == "schedule").current
    b1 = next(m for m in ex.members if m.tag == "B1")
    assert b1.width_m == pytest.approx(0.23) and b1.flags


def test_typed_answers_are_understood(plan):
    _, _, qs = _read(plan)
    q = next(q for q, _ in qs if q.key == "beam-width:B1")
    assert interpret_rules(q, "the schedule is right").option_id == "schedule"
    assert interpret_rules(q, "use 300").option_id == "drawing"
    assert interpret_rules(q, "not the schedule").option_id == "drawing"
    r = interpret_rules(q, "it's 250 mm")
    assert r.understood and r.custom_values == {"width_m": 250.0} and "250 mm" in r.understood_as
    assert not interpret_rules(q, "hmm no idea").understood
    rule = next(q for q, _ in qs if q.key == "rule:slab-over-beam")
    assert interpret_rules(rule, "PM says IS 1200 - slab over the beams").option_id == "slab"


def test_apply_record_and_undo(plan):
    _, ex, qs = _read(plan)
    job = _job(ex, qs)
    q = next(q for q in job.questions if q.key == "beam-width:B1")
    d = apply_answer(job, q, AnswerRequest(option_id="drawing", answer_text="use the drawing", interpreted_by="rules"), "aman@test")
    b1 = next(m for m in job.elements.members if m.tag == "B1")
    assert b1.width_m == pytest.approx(0.30) and not b1.flags and b1.confidence == 1.0
    assert q.status == "answered" and d.decided_by == "aman@test" and d.answer_text == "use the drawing"
    with pytest.raises(QuestionError):
        apply_answer(job, q, AnswerRequest(option_id="schedule"), "x")      # answered twice
    undo_decision(job, d, "aman@test")
    assert b1.width_m == pytest.approx(0.23) and b1.flags and q.status == "open" and d.undone


def test_slab_over_beam_moves_concrete_but_keeps_the_total(plan):
    _, ex, qs = _read(plan)
    job = _job(ex, qs)
    before = compute_measurement(job.elements)
    def tot(r, code):
        return sum(b.total for b in r.blocks if b.item_code == code)

    q = next(q for q in job.questions if q.key == "rule:slab-over-beam")
    d = apply_answer(job, q, AnswerRequest(option_id="slab", answer_text="IS 1200"), "aman@test")
    b1 = next(m for m in job.elements.members if m.tag == "B1")
    assert b1.slab_thickness_m == pytest.approx(0.15)
    strip = next(s for s in job.elements.slabs if s.tag.startswith("Over beams"))
    assert strip.soffit_formwork is False
    after = compute_measurement(job.elements)
    concrete_before = tot(before, "RCC-SLAB") + tot(before, "RCC-BEAM")
    concrete_after = tot(after, "RCC-SLAB") + tot(after, "RCC-BEAM")
    assert concrete_after == pytest.approx(concrete_before, abs=0.002)      # moved, not created
    assert tot(after, "RCC-BEAM") < tot(before, "RCC-BEAM")
    assert tot(after, "FW-SLAB") == pytest.approx(tot(before, "FW-SLAB"), abs=0.01)   # no soffit under the strip
    undo_decision(job, d, "aman@test")
    assert not any(s.tag.startswith("Over beams") for s in job.elements.slabs) and b1.slab_thickness_m == 0


def test_answers_survive_a_reread(plan):
    _, ex, qs = _read(plan)
    job = _job(ex, qs)
    q = next(q for q in job.questions if q.key == "beam-width:B1")
    apply_answer(job, q, AnswerRequest(custom_values={"width_m": 250}, answer_text="it's 250"), "aman@test")
    _, ex2, qs2 = _read(plan)                         # the drawing is read again: new elements, new ids
    job.elements, job.questions = ex2, [q for q, _ in qs2]
    notes = reapply_decisions(job)
    assert notes and "Re-applied" in notes[0]
    assert next(m for m in job.elements.members if m.tag == "B1").width_m == pytest.approx(0.25)
    assert len([d for d in job.decisions if not d.undone]) == 1


# ------------------------------------------------------------------ the API, end to end
@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def h(client):
    for pw in ("Test-Admin-123", "New-Admin-Pass-1"):
        r = client.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": pw})
        if r.status_code == 200:
            return {"Authorization": f"Bearer {r.json()['access_token']}"}
    raise AssertionError("cannot log in as the test admin")


def test_question_flow_over_the_api(client, h, plan):
    with open(plan, "rb") as fh:
        r = client.post("/api/v1/jobs", data={"module": "measurement", "project_name": "Q", "level": "T"},
                        files=[("files", ("beam_layout_test.dxf", fh, "application/dxf"))], headers=h)
    assert r.status_code == 202, r.text
    jid = r.json()["job_id"]
    for _ in range(240):
        job = client.get(f"/api/v1/jobs/{jid}", headers=h).json()
        if job["status"] in ("ready", "failed"):
            break
        time.sleep(0.5)
    assert job["status"] == "ready", job.get("error")
    q = next(q for q in job["questions"] if q["key"] == "beam-width:B1")
    pic = client.get(f"/api/v1/jobs/{jid}/questions/{q['id']}/picture", headers=h)
    assert pic.status_code == 200 and pic.headers["content-type"] == "image/png"

    r = client.post(f"/api/v1/jobs/{jid}/questions/{q['id']}/interpret", json={"text": "the drawing is right"}, headers=h)
    it = r.json()
    assert r.status_code == 200 and it["understood"] and it["option_id"] == "drawing"
    unchanged = client.get(f"/api/v1/jobs/{jid}", headers=h).json()          # interpreting changes nothing
    assert next(m for m in unchanged["elements"]["members"] if m["tag"] == "B1")["width_m"] == pytest.approx(0.23)

    r = client.post(f"/api/v1/jobs/{jid}/questions/{q['id']}/answer", headers=h,
                    json={"option_id": it["option_id"], "answer_text": "the drawing is right",
                          "understood_as": it["understood_as"], "interpreted_by": it["via"]})
    assert r.status_code == 200, r.text
    job = r.json()
    assert next(m for m in job["elements"]["members"] if m["tag"] == "B1")["width_m"] == pytest.approx(0.30)
    d = job["decisions"][-1]
    assert d["answer_text"] == "the drawing is right" and d["decided_by"] == "admin@test.local"
    assert client.post(f"/api/v1/jobs/{jid}/questions/{q['id']}/answer", json={"option_id": "schedule"}, headers=h).status_code == 409

    r = client.post(f"/api/v1/jobs/{jid}/decisions/{d['id']}/undo", headers=h)
    assert r.status_code == 200
    job = r.json()
    assert next(m for m in job["elements"]["members"] if m["tag"] == "B1")["width_m"] == pytest.approx(0.23)
    assert next(x for x in job["questions"] if x["id"] == q["id"])["status"] == "open"
