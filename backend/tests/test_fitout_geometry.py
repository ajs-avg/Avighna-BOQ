"""The CAD measurer must reproduce the quantities in the consultant's BOQ for the Dubai office
floor finishes plan (FC-201 stone 270 m2, FC-202 carpet 175 m2) from the DXF geometry alone."""
import gzip
import shutil
from pathlib import Path

from app.extract.fitout_geometry import measure_dxf
from app.extract.heuristics import fitout_items_from_facts

FIX = Path(__file__).parent / "fixtures" / "GA-103_floor_finishes.dxf.gz"


def _dxf(tmp_path):
    out = tmp_path / "GA-103.dxf"
    with gzip.open(FIX, "rb") as src, open(out, "wb") as dst:
        shutil.copyfileobj(src, dst)
    return out


def test_floor_finish_areas_match_consultant_boq(tmp_path):
    facts = measure_dxf(_dxf(tmp_path))
    assert facts.units == "mm"
    areas = facts.area_by_code()
    assert abs(areas["FC-201"] - 270) / 270 < 0.02      # stone: 271.8 measured vs 270 in BOQ
    assert abs(areas["FC-202"] - 175) / 175 < 0.02      # carpet: 174.7 measured vs 175 in BOQ
    assert 15 < areas["FC-203"] < 30                     # pantry tile
    rooms = facts.rooms_by_code()
    assert "SALES AREA" in rooms["FC-201"] and "BOARDROOM" in rooms["FC-202"] and rooms["FC-203"] == ["PANTRY"]
    sources = {h.code_source for h in facts.hatches}
    assert "leader from tag" in sources


def test_items_from_facts_without_ai(tmp_path):
    facts = measure_dxf(_dxf(tmp_path))
    ex = fitout_items_from_facts(facts, "GA-103", "floor_finishes_plan")
    codes = {i.code: i for i in ex.items}
    assert codes["FC-201"].unit == "m2" and codes["FC-201"].qty_basis == "measured" and codes["FC-201"].qty > 260
    assert codes["FC-202"].section == "Floor Finishes" and "BOARDROOM" in codes["FC-202"].rooms


def test_sortentstable_stripping_keeps_dxf_loadable(tmp_path):
    import ezdxf
    from app.extract.dwg_convert import _strip_dxf_objects, sanitize_dxf
    doc = ezdxf.new("R2018")
    doc.modelspace().add_line((0, 0), (1, 1))
    p = tmp_path / "x.dxf"
    doc.saveas(p)
    text = p.read_text()
    # inject a malformed SORTENTSTABLE object into the OBJECTS section like LibreDWG 0.13 does
    bad = "  0\nSORTENTSTABLE\n  5\nFFFF\n330\n0\n100\nAcDbSortentsTable\n331\n1F\n"
    text = text.replace("  0\nENDSEC\n  0\nEOF", bad + "  0\nENDSEC\n  0\nEOF")
    p.write_text(text)
    assert "SORTENTSTABLE" in p.read_text()
    assert sanitize_dxf(p) is True                      # loadable afterwards (stripped only if ezdxf rejects it)
    assert len(list(ezdxf.readfile(str(p)).modelspace())) == 1
    stripped = _strip_dxf_objects(p.read_text())
    assert "SORTENTSTABLE" not in stripped and "ENDSEC" in stripped and "EOF" in stripped
    assert len(list(ezdxf.read(__import__("io").StringIO(stripped)).modelspace())) == 1
