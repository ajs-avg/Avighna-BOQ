"""Render one DXF layout to PNG in a *separate process* (DWG-converted model spaces can be huge;
an out-of-memory kill must never take the API down). Usage:
    python -m app.extract.render_cli <dxf> <layout> <out.png> <max_px> <dpi>
"""
from __future__ import annotations

import io
import sys
from pathlib import Path


def render(path: Path, layout_name: str, max_px: int, dpi: int) -> bytes:
    import ezdxf
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import (
        BackgroundPolicy, ColorPolicy, Configuration, HatchPolicy, LineweightPolicy,
    )
    from ezdxf.addons.drawing import layout as dlayout
    from ezdxf.addons.drawing import pymupdf as pymupdf_backend

    try:
        doc = ezdxf.readfile(str(path))
    except ezdxf.DXFStructureError:
        from ezdxf import recover
        doc, _ = recover.readfile(str(path))
    try:
        doc.audit()
    except Exception:
        pass
    for lay in [doc.modelspace()] + [doc.layout(n) for n in doc.layout_names_in_taborder() if n.lower() != "model"]:
        for e in list(lay.query("INSERT")):
            if e.dxf.name not in doc.blocks:
                lay.delete_entity(e)
    layout = doc.modelspace() if layout_name.lower() == "model" else doc.layout(layout_name)
    ctx = RenderContext(doc)
    ctx.set_current_layout(layout)
    try:
        ctx.current_layout_properties.set_colors("#FFFFFF")
    except Exception:
        pass
    cfg = Configuration().with_changes(
        hatch_policy=HatchPolicy.SHOW_OUTLINE,          # pattern fills would explode into millions of lines
        lineweight_policy=LineweightPolicy.RELATIVE,
        min_lineweight=0.15,
        max_flattening_distance=0.5,
        background_policy=BackgroundPolicy.WHITE,       # plot-style black on white (draw_layout resets layout colors)
        color_policy=ColorPolicy.BLACK,
    )
    backend = pymupdf_backend.PyMuPdfBackend()
    Frontend(ctx, backend, config=cfg).draw_layout(layout, finalize=True)
    # Fixed paper size: never let the page auto-size to the drawing extents (a stray entity far
    # from the plan would otherwise demand a multi-gigapixel pixmap).
    width_mm, height_mm = 841.0, 594.0  # A1 landscape
    if not layout.is_modelspace:
        try:
            pw, ph = float(layout.dxf.paper_width), float(layout.dxf.paper_height)
            if 100 < pw < 3000 and 100 < ph < 3000:
                width_mm, height_mm = (max(pw, ph), min(pw, ph))
        except Exception:
            pass
    else:
        try:
            from ezdxf import bbox as _bbox
            box = _bbox.extents(layout, fast=True)
            if box.has_data and box.size.x > 0 and box.size.y > 0:
                if box.size.y > box.size.x:
                    width_mm, height_mm = 594.0, 841.0
        except Exception:
            pass
    page = dlayout.Page(width_mm, height_mm, dlayout.Units.mm, margins=dlayout.Margins.all(5))
    settings = dlayout.Settings(fit_page=True)
    png = backend.get_pixmap_bytes(page, fmt="png", settings=settings, dpi=dpi)
    from PIL import Image
    im = Image.open(io.BytesIO(png))
    if max(im.size) > max_px:
        r = max_px / max(im.size)
        im = im.convert("RGB").resize((max(1, int(im.width * r)), max(1, int(im.height * r))))
        out = io.BytesIO()
        im.save(out, format="PNG", optimize=True)
        return out.getvalue()
    return png


if __name__ == "__main__":
    src, layout, out, max_px, dpi = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
    data = render(Path(src), layout, max_px, dpi)
    Path(out).write_bytes(data)
    print(len(data))
