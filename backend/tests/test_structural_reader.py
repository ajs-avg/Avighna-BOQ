"""Structural DXF reader: synthetic-drawing tests.

Builds a tiny structural plan in memory with ezdxf (two columns, one beam drawn as
two parallel lines, labels, a beam schedule off to the side, and a crossed-out old
table) and checks that the reader finds the members, lengths, schedule and
exclusions. The full method is validated against the Nishika Elysium 14th floor
(see the module docstring of app.extract.structural).
"""
from __future__ import annotations

import math

import ezdxf
import pytest

from app.extract.structural import read_structural_dxf, structural_to_measurement
from app.extract.structural.config import StructuralConfig
from app.extract.structural.entities import extract_entities
from app.extract.structural.exclusions import find_excluded
from app.extract.structural.schedule import parse_beam_schedule


def _text(msp, s, x, y, layer, h=200.0, rot=0.0):
    msp.add_text(s, dxfattribs={"layer": layer, "height": h, "rotation": rot, "insert": (x, y)})


def _col_hatch(msp, x0, y0, x1, y1, layer="column hatch", color=256):
    h = msp.add_hatch(dxfattribs={"layer": layer})
    if color != 256:
        h.dxf.color = color
    h.paths.add_polyline_path([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], is_closed=True)


@pytest.fixture()
def plan(tmp_path):
    """Two 300x600 columns 5 m apart, one 230-wide beam B1 between their faces,
    a slab tag, a 3-row beam schedule 60 m to the right, and a crossed-out old
    table beyond it."""
    doc = ezdxf.new("R2018")
    doc.layers.add("BEAM")
    for name in ("BEAM NO.", "BEAM SIZES", "COLUMN SIZE", "S-COLS-NUM", "Text", "SLAB", "column hatch"):
        if name not in doc.layers:
            doc.layers.add(name)
    msp = doc.modelspace()

    # columns at x = 0..300 and x = 5300..5600, y = 0..600
    _col_hatch(msp, 0, 0, 300, 600)
    _col_hatch(msp, 5300, 0, 5600, 600)
    _text(msp, "C1", 60, 700, "S-COLS-NUM")
    _text(msp, "(300X600)", 60, 420, "COLUMN SIZE")
    _text(msp, "C2", 5360, 700, "S-COLS-NUM")
    _text(msp, "(300X600)", 5360, 420, "COLUMN SIZE")

    # beam B1: two horizontal edge lines 230 apart, through the columns
    msp.add_line((0, 185), (5600, 185), dxfattribs={"layer": "BEAM"})
    msp.add_line((0, 415), (5600, 415), dxfattribs={"layer": "BEAM"})
    _text(msp, "B1", 2500, 450, "BEAM NO.")
    _text(msp, "(230X750)", 2500, 100, "BEAM SIZES")

    # a slab panel above the beam, closed by slab-layer lines, with a tag
    msp.add_line((300, 415), (5300, 415), dxfattribs={"layer": "SLAB"})
    msp.add_line((300, 3415), (5300, 3415), dxfattribs={"layer": "SLAB"})
    msp.add_line((300, 415), (300, 3415), dxfattribs={"layer": "SLAB"})
    msp.add_line((5300, 415), (5300, 3415), dxfattribs={"layer": "SLAB"})
    _text(msp, "S1", 2800, 2000, "COLUMN SIZE")
    _text(msp, "150 THK", 2800, 1600, "Text")

    # beam schedule, far to the right: name | B | D | remark
    for i, (nm, b, d, rem) in enumerate([("B1", "230", "750", ""), ("B2", "300", "600", "CANTILEVER"),
                                         ("B3,B4", "200", "450", "")]):
        y = -i * 900
        _text(msp, nm, 60000, y, "Text")
        _text(msp, b, 62500, y, "Text")
        _text(msp, d, 64500, y, "Text")
        if rem:
            _text(msp, rem, 66500, y, "Text")

    # an old crossed-out table with a stale beam row inside
    _text(msp, "B9", 80000, 0, "Text")
    _text(msp, "999", 82500, 0, "Text")
    msp.add_line((79000, -6000), (90000, 6000))
    msp.add_line((79000, 6000), (90000, -6000))
    msp.add_line((79000, -6000), (90000, -6000))

    path = tmp_path / "plan.dxf"
    doc.saveas(path)
    return path


def test_reader_finds_members_and_lengths(plan):
    res = read_structural_dxf(plan, StructuralConfig(plan_region=[-1000, -3000, 10000, 5000]))
    # columns
    names = sorted(c.name for c in res.columns if c.name)
    assert names == ["C1", "C2"]
    assert all(not c.flags for c in res.columns)
    # beam: clear span between the column faces = 5300 - 300 = 5000
    assert "B1" in res.beams
    b = res.beams["B1"][0]
    assert b.width == 230
    assert abs(b.length_mm - 5000) <= 60
    assert not b.flags
    # slab panel found with its thickness note
    s1 = [s for s in res.slabs if s.tag == "S1"]
    assert s1 and s1[0].found
    assert s1[0].thickness_mm == 150
    assert abs(s1[0].area_m2 - 15.0) < 1.5


def test_schedule_rows_and_exclusions(plan):
    doc = ezdxf.readfile(str(plan))
    words, boxes = find_excluded(doc)
    assert len(boxes) == 1          # the crossed-out table, and nothing else
    raw = extract_entities(doc, StructuralConfig(plan_region=[-1000, -3000, 10000, 5000]))
    sched = parse_beam_schedule(raw.texts, [-1000.0, -3000.0, 10000.0, 5000.0], boxes)
    assert sched.by_name["B1"].B == 230 and sched.by_name["B1"].D == 750
    assert sched.by_name["B2"].kind == "cantilever"
    assert sched.by_name["B3"].B == 200 and sched.by_name["B4"].B == 200
    assert "B9" not in sched.by_name   # inside the crossed-out box


def test_mapping_to_measurement(plan):
    res = read_structural_dxf(plan, StructuralConfig(plan_region=[-1000, -3000, 10000, 5000]))
    ex = structural_to_measurement(res, "plan.dxf [Model]", level="test floor")
    beams = [m for m in ex.members if m.kind == "beam"]
    cols = [m for m in ex.members if m.kind == "column"]
    assert len(beams) == 1 and len(cols) == 2
    assert abs(beams[0].length_m - 5.0) < 0.07
    assert beams[0].width_m == pytest.approx(0.23)
    assert beams[0].outline            # positions kept for the check picture
    assert ex.slabs and ex.slabs[0].thickness_m == pytest.approx(0.15)
    # area preserved through the length x width mapping
    assert ex.slabs[0].length_m * ex.slabs[0].width_m == pytest.approx(res.slabs[0].area_m2, rel=0.02)
    assert any("heights are assumed" in w for w in ex.warnings)
