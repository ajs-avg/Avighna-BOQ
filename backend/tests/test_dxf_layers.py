"""LibreDWG 0.13 writes every layer with a negative colour (= 'off'); the loader must switch them on
so the renderer and the geometry reader see the drawing."""
from pathlib import Path

import ezdxf

from app.extract.dwg_convert import load_dxf_lenient, normalise_layers
from app.extract.dxf_reader import render_layout_png


def _write_all_off_dxf(path: Path) -> None:
    doc = ezdxf.new("R2018")
    for name, color in (("WALL", 1), ("DOOR", 3), ("TEXT", 7)):
        doc.layers.add(name, color=color)
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (5000, 0), (5000, 3000), (0, 3000)], close=True, dxfattribs={"layer": "WALL"})
    msp.add_line((1000, 0), (1900, 0), dxfattribs={"layer": "DOOR"})
    msp.add_text("BEDROOM", dxfattribs={"layer": "TEXT", "height": 200}).set_placement((2000, 1500))
    for lay in doc.layers:  # what LibreDWG does
        lay.dxf.color = -abs(int(lay.dxf.color))
    doc.saveas(path)


def test_all_off_layers_are_switched_on(tmp_path: Path) -> None:
    p = tmp_path / "off.dxf"
    _write_all_off_dxf(p)
    raw = ezdxf.readfile(str(p))
    assert all(lay.is_off() for lay in raw.layers)
    doc = load_dxf_lenient(p)
    assert not any(lay.is_off() for lay in doc.layers if lay.dxf.name != "Defpoints")
    assert normalise_layers(doc) == 0  # idempotent


def test_single_off_layer_is_respected(tmp_path: Path) -> None:
    doc = ezdxf.new("R2018")
    doc.layers.add("A", color=1)
    doc.layers.add("B", color=2)
    doc.layers.add("HIDDEN", color=3).off()  # negative colour on one layer only
    p = tmp_path / "one_off.dxf"
    doc.saveas(p)
    doc2 = load_dxf_lenient(p)
    assert doc2.layers.get("HIDDEN").is_off()  # a genuinely hidden layer stays hidden


def test_render_of_all_off_dxf_is_not_blank(tmp_path: Path) -> None:
    p = tmp_path / "off.dxf"
    _write_all_off_dxf(p)
    png = render_layout_png(p, "Model", max_px=800, dpi=50, timeout_s=120)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    import io
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("L")
    dark = sum(1 for v in im.getdata() if v < 128)
    assert dark > 50, "rendered page is blank: the layers were not switched on"
