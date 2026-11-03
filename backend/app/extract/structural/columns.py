"""Match column/wall hatches with their name tags and size labels.

A column is an exact filled hatch, so its drawn size is trusted. The name (C1, L3,
FC10, W1...) and the size label "(230X2570)" are separate texts; each name pairs
with the size written just under it, and the pair goes to the nearest hatch whose
drawn size fits the written size (the "size fit" that stops a label landing on the
neighbouring lift wall). All distances in mm.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from app.extract.structural.config import StructuralConfig
from app.extract.structural.entities import ColumnHatch, TextItem

COL_TAG_RX = re.compile(r"^(FC|HC|C|L|W)(\d{0,2}[A-Z]?)$")
SIZE_RX = re.compile(r"^\(?(\d{3})X(\d{3,4})(/\d{3})?\)?$")


@dataclass
class ColumnResult:
    name: Optional[str]
    size: Optional[Tuple[int, int]]        # written size (W, L) mm
    measured: Tuple[int, int]              # drawn size (min, max) mm
    kind: str                              # column/wall | hanging | floating column
    bbox: List[float]
    polys: List[List[Tuple[float, float]]]
    flags: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.name) and not self.flags


def _ctr(bb: Sequence[float]) -> Tuple[float, float]:
    return ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)


def _d_box(p: Tuple[float, float], bb: Sequence[float]) -> float:
    dx = max(bb[0] - p[0], 0, p[0] - bb[2])
    dy = max(bb[1] - p[1], 0, p[1] - bb[3])
    return math.hypot(dx, dy)


def _greedy(pairs: List[Tuple[float, int, int]], maxd: float) -> Dict[int, Tuple[int, float]]:
    pairs.sort()
    used_a, used_b = set(), set()
    out: Dict[int, Tuple[int, float]] = {}
    for d, a, b in pairs:
        if d > maxd or a in used_a or b in used_b:
            continue
        used_a.add(a)
        used_b.add(b)
        out[a] = (b, d)
    return out


def _measured(c: ColumnHatch) -> Tuple[int, int]:
    x0, y0, x1, y1 = c.bbox
    return (round(min(x1 - x0, y1 - y0)), round(max(x1 - x0, y1 - y0)))


def _fits(size: Tuple[int, int], c: ColumnHatch) -> bool:
    mw, ml = _measured(c)
    return abs(size[0] - mw) <= 25 and abs(size[1] - ml) <= max(40, 0.03 * size[1])


def match_columns(columns: List[ColumnHatch], texts: Sequence[TextItem],
                  cfg: StructuralConfig) -> List[ColumnResult]:
    tags = [t for t in texts if t.layer in cfg.column_tag_layers
            and COL_TAG_RX.match(t.text.replace(" ", "").upper())]
    sizes = []
    for t in texts:
        if t.layer not in cfg.column_size_layers:
            continue
        m = SIZE_RX.match(t.text.replace(" ", "").upper())
        if m:
            sizes.append((t, (int(m.group(1)), int(m.group(2)))))

    # 1) pair each name with the size written just under it (~280 mm below)
    def tag_size_cost(t: TextItem, z: TextItem) -> float:
        dy = t.cy - z.cy        # positive when the size sits below the name
        return abs(t.cx - z.cx) + (abs(dy - 280) if dy > 0 else 2000)

    m_ts = _greedy([(tag_size_cost(t, z), i, j) for i, t in enumerate(tags)
                    for j, (z, _s) in enumerate(sizes)], maxd=400)
    groups: List[Dict] = []
    used_z = set()
    for i, t in enumerate(tags):
        z = sizes[m_ts[i][0]] if i in m_ts else None
        if z is not None:
            used_z.add(m_ts[i][0])
        groups.append(dict(tag=t.text.replace(" ", "").upper(),
                           size=z[1] if z else None,
                           pos=(t.cx, t.cy) if z is None else (z[0].cx, z[0].cy)))
    for j, (z, s) in enumerate(sizes):
        if j not in used_z:
            groups.append(dict(tag=None, size=s, pos=(z.cx, z.cy)))

    # 2) each group goes to the nearest hatch; a size that does not fit the drawn
    #    shape costs an extra 1000 mm, so the fitting hatch wins
    pairs = []
    for ci, c in enumerate(columns):
        for gi, g in enumerate(groups):
            d = _d_box(g["pos"], c.bbox)
            if g["size"] is not None and not _fits(g["size"], c):
                d += 1000
            pairs.append((d, ci, gi))
    m_cg = _greedy(pairs, maxd=1400)

    out: List[ColumnResult] = []
    for ci, c in enumerate(columns):
        g = groups[m_cg[ci][0]] if ci in m_cg else None
        name = g["tag"] if g else None
        size = tuple(g["size"]) if g and g["size"] else None
        mw, ml = _measured(c)
        flags: List[str] = []
        if size and not _fits(size, c):
            flags.append(f"label says {size[0]}x{size[1]} but the shape measures {mw}x{ml}")
        if not name and c.kind == "column/wall":
            flags.append("no name found for this column/wall")
        out.append(ColumnResult(name=name, size=size, measured=(mw, ml), kind=c.kind,
                                bbox=list(c.bbox), polys=c.polys, flags=flags))
    return out
