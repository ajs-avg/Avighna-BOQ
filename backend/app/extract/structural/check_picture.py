"""The coloured check picture: everything the reader found, drawn over a clean
plan so a person can check the whole floor at a glance.

Green = read cleanly (name, size and geometry agree). Amber = found, but flagged
(plan vs schedule disagree, default applied, no panel...). Grey = small members
(brackets, HB) with no schedule row. Returns PNG bytes.
"""
from __future__ import annotations

import io
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from app.extract.structural.reader import StructuralReadResult

GREEN = (26, 140, 55)
AMBER = (230, 140, 0)
GREY = (110, 110, 110)

_FONTS = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
          "/System/Library/Fonts/Helvetica.ttc")


def _font(size: int):
    for path in _FONTS:
        try:
            return ImageFont.truetype(path, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def render_check_picture(res: StructuralReadResult, max_px: int = 2600) -> Optional[bytes]:
    xs: List[float] = []
    ys: List[float] = []
    for c in res.columns:
        xs += [c.bbox[0], c.bbox[2]]
        ys += [c.bbox[1], c.bbox[3]]
    for v in res.beams.values():
        for b in v:
            xs += [q[0] for q in b.geom]
            ys += [q[1] for q in b.geom]
    if not xs:
        return None
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    pad = 0.03 * max(x1 - x0, y1 - y0)
    x0, x1, y0, y1 = x0 - pad, x1 + pad, y0 - pad, y1 + pad
    sc = max_px / max(x1 - x0, y1 - y0)
    W, H = int((x1 - x0) * sc), int((y1 - y0) * sc)
    legend_h = 150
    im = Image.new("RGB", (W, H + legend_h), (255, 255, 255))
    dr = ImageDraw.Draw(im, "RGBA")
    F = _font(max(11, int(0.0035 * max_px)))

    def P(x: float, y: float) -> Tuple[float, float]:
        return ((x - x0) * sc, (y1 - y) * sc)   # DXF y grows up; image y grows down

    for s in res.slabs:       # slabs first (light fill)
        if not s.found or len(s.poly) < 3:
            continue
        col = AMBER if s.flags else GREEN
        dr.polygon([P(x, y) for x, y in s.poly], fill=col + (30,), outline=col + (110,))
    for c in res.columns:     # columns
        col = AMBER if c.flags else GREEN
        b = c.bbox
        dr.rectangle([P(b[0], b[3]), P(b[2], b[1])], fill=col + (215,), outline=(0, 0, 0, 255))
    for name, v in res.beams.items():   # beams
        for b in v:
            col = GREY if name.startswith(("BKT", "HB")) else (AMBER if b.flags else GREEN)
            pts = [P(x, y) for x, y in b.geom]
            if len(pts) >= 2:
                dr.line(pts, fill=col + (205,), width=max(3, int(b.width * sc)))
    for name, v in res.beams.items():   # labels on top
        for b in v:
            if len(b.geom) < 2:
                continue
            pts = [P(x, y) for x, y in b.geom]
            mx, my = pts[len(pts) // 2]
            col = GREY if name.startswith(("BKT", "HB")) else (AMBER if b.flags else GREEN)
            w = dr.textlength(name, font=F)
            dr.rounded_rectangle([mx - w / 2 - 3, my - 9, mx + w / 2 + 3, my + 9], radius=3,
                                 fill=(255, 255, 255, 225), outline=col + (255,), width=1)
            dr.text((mx, my), name, font=F, fill=col, anchor="mm")

    FL = _font(max(14, int(0.006 * max_px)))
    items = [(GREEN, "Read cleanly: name, size and geometry agree"),
             (AMBER, "Flagged: needs a person's look (see the element's notes)"),
             (GREY, "Bracket / small member without a schedule row")]
    y = H + 18
    for col, txt in items:
        dr.rectangle([20, y, 56, y + 24], fill=col + (215,), outline=col)
        dr.text((66, y + 12), txt, font=FL, fill=(30, 30, 30), anchor="lm")
        y += 42
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
