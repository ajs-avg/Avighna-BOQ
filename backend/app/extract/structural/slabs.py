"""Slab panels: the closed areas enclosed by beam lines, slab-layer lines and
column outlines. The slab tag (S3, S13...) sits inside one panel; that panel is
the slab, with its real outline (L-shapes included), not a guessed rectangle."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from shapely.geometry import LineString, Point
from shapely.ops import polygonize, unary_union

from app.extract.structural.config import StructuralConfig
from app.extract.structural.entities import ColumnHatch, Prim, TextItem

SLAB_TAG_RX = re.compile(r"^S\d+[A-Z]?$")
THK_RX = re.compile(r"(\d{2,3})\s*(?:MM)?\s*(?:THK|THICK)|RCC\s*SLAB\s*(\d{2,3})", re.I)


@dataclass
class SlabResult:
    tag: str
    found: bool
    x: float
    y: float
    area_m2: float = 0.0
    a_mm: int = 0                   # minimum rotated rectangle sides
    b_mm: int = 0
    rect_fill: float = 1.0          # area / rectangle area; < 1 means L-shaped etc.
    thickness_mm: Optional[int] = None
    flags: List[str] = field(default_factory=list)
    poly: List[Tuple[float, float]] = field(default_factory=list)


def find_slabs(prims: Sequence[Prim], columns: Sequence[ColumnHatch], texts: Sequence[TextItem],
               slab_schedule: Dict[str, int], cfg: StructuralConfig,
               region: Optional[List[float]]) -> List[SlabResult]:
    lines = [LineString(p.points()) for p in prims
             if (p.kind == "arc" or math.dist(p.a, p.b) > 30)]
    for c in columns:
        for pl in c.polys:
            if len(pl) >= 3:
                lines.append(LineString(list(pl) + [pl[0]]))
    ext = []
    for g in lines:    # stretch straight lines 40 mm so near-touching ends meet
        cs = list(g.coords)
        if len(cs) == 2:
            (x1, y1), (x2, y2) = cs
            L = math.dist(cs[0], cs[1]) or 1
            ux, uy = (x2 - x1) / L, (y2 - y1) / L
            ext.append(LineString([(x1 - ux * 40, y1 - uy * 40), (x2 + ux * 40, y2 + uy * 40)]))
        else:
            ext.append(g)
    polys = [p for p in polygonize(unary_union(ext)) if p.area > 200_000]   # > 0.2 m²

    def in_region(t: TextItem) -> bool:
        return region is None or (region[0] <= t.cx <= region[2] and region[1] <= t.cy <= region[3])

    tags = [t for t in texts if t.layer in cfg.slab_tag_layers and in_region(t)
            and SLAB_TAG_RX.match(t.text.replace(" ", "").upper())]
    notes = [t for t in texts if in_region(t)]

    out: List[SlabResult] = []
    for t in tags:
        tag = t.text.replace(" ", "").upper()
        p = Point(t.cx, t.cy)
        inside = [g for g in polys if g.contains(p)]
        if not inside:
            out.append(SlabResult(tag=tag, found=False, x=t.cx, y=t.cy,
                                  flags=["no closed panel found around this tag"]))
            continue
        g = min(inside, key=lambda g: g.area)
        mrr = g.minimum_rotated_rectangle
        cs = list(mrr.exterior.coords)
        s1, s2 = math.dist(cs[0], cs[1]), math.dist(cs[1], cs[2])
        res = SlabResult(tag=tag, found=True, x=t.cx, y=t.cy,
                         area_m2=round(g.area / 1e6, 3),
                         a_mm=round(min(s1, s2)), b_mm=round(max(s1, s2)),
                         rect_fill=round(g.area / mrr.area, 2) if mrr.area else 1.0,
                         poly=list(g.exterior.coords))
        res.thickness_mm = slab_schedule.get(tag)
        if res.thickness_mm is None:   # a thickness note inside the panel, e.g. "RCC SLAB 175 THK"
            for n in notes:
                if not g.contains(Point(n.cx, n.cy)):
                    continue
                m = THK_RX.search(n.text)
                if m:
                    res.thickness_mm = int(m.group(1) or m.group(2))
                    break
        if res.thickness_mm is None:
            res.thickness_mm = cfg.default_slab_thickness_mm
            res.flags.append(f"thickness not found: default {cfg.default_slab_thickness_mm} mm applied")
        out.append(res)
    return out
