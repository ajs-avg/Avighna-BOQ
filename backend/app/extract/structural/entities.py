"""Pull the raw entities a structural reader needs out of an ezdxf document.

Everything stays in DXF drawing units (mm). Output is plain dicts/lists so the
rest of the reader is geometry-only and easy to test.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ezdxf.math import Vec2

from app.extract.structural.config import StructuralConfig

Point = Tuple[float, float]


@dataclass
class ColumnHatch:
    bbox: List[float]                  # x0, y0, x1, y1 (mm)
    polys: List[List[Point]]
    kind: str                          # column/wall | hanging | floating column
    aci: int


@dataclass
class Prim:
    kind: str                          # line | arc
    layer: str
    aci: int
    a: Optional[Point] = None          # line
    b: Optional[Point] = None
    c: Optional[Point] = None          # arc centre
    r: float = 0.0
    sa: float = 0.0                    # arc angles, degrees
    ea: float = 0.0

    def points(self, max_step_deg: float = 3.0) -> List[Point]:
        if self.kind == "line":
            return [self.a, self.b]
        sa, ea = self.sa, self.ea
        if ea < sa:
            ea += 360
        n = max(4, int((ea - sa) / max_step_deg))
        return [(self.c[0] + self.r * math.cos(math.radians(sa + (ea - sa) * i / n)),
                 self.c[1] + self.r * math.sin(math.radians(sa + (ea - sa) * i / n))) for i in range(n + 1)]

    def length(self) -> float:
        if self.kind == "line":
            return math.dist(self.a, self.b)
        span = (self.ea - self.sa) % 360 or 360
        return self.r * math.radians(span)


@dataclass
class TextItem:
    text: str
    layer: str
    x: float                           # insert point
    y: float
    cx: float                          # approximate centre of the text box
    cy: float
    rot: float
    h: float


@dataclass
class RawEntities:
    columns: List[ColumnHatch] = field(default_factory=list)
    prims: List[Prim] = field(default_factory=list)          # on beam/slab layers, in region
    texts: List[TextItem] = field(default_factory=list)      # ALL text (plan + schedules)
    region: Optional[List[float]] = None                     # the plan region actually used
    notes: List[str] = field(default_factory=list)


def _hatch_polys(h) -> List[List[Point]]:
    out: List[List[Point]] = []
    for p in h.paths:
        pts: List[Point] = []
        if hasattr(p, "vertices"):
            pts = [(v[0], v[1]) for v in p.vertices]
        else:
            for e in p.edges:
                if getattr(e, "type", None) is not None and getattr(e.type, "name", "") == "LINE" \
                        or e.__class__.__name__ == "LineEdge":
                    pts += [(e.start[0], e.start[1]), (e.end[0], e.end[1])]
                elif hasattr(e, "start_point"):
                    pts += [tuple(e.start_point)[:2], tuple(e.end_point)[:2]]
        if len(pts) >= 3:
            out.append(pts)
    return out


def _text_centre(e, text: str) -> Tuple[float, float, float, float]:
    """Centre of the text box, rotation and height for a TEXT/MTEXT entity."""
    p = e.dxf.insert
    rot = e.dxf.get("rotation", 0)
    h = e.dxf.get("height", 0) if e.dxftype() == "TEXT" else e.dxf.get("char_height", 0)
    L = len(text) * h * 0.8
    ang = math.radians(rot)
    cx = p.x + math.cos(ang) * L / 2 - math.sin(ang) * h / 2
    cy = p.y + math.sin(ang) * L / 2 + math.cos(ang) * h / 2
    if e.dxftype() == "TEXT" and (e.dxf.get("halign", 0) or e.dxf.get("valign", 0)):
        ap = e.dxf.get("align_point", None)
        if ap is not None:
            cx, cy = ap.x, ap.y
            if e.dxf.get("valign", 0) in (0, 1):
                cx, cy = ap.x - math.sin(ang) * h / 2, ap.y + math.cos(ang) * h / 2
    return cx, cy, rot, h


def _clusters(points: Sequence[Point], link: float) -> List[List[int]]:
    """Union-find clustering of points linked when closer than `link`."""
    parent = list(range(len(points)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            if abs(points[i][0] - points[j][0]) > link:
                continue
            if math.dist(points[i], points[j]) < link:
                a, b = find(i), find(j)
                if a != b:
                    parent[a] = b
    groups: Dict[int, List[int]] = {}
    for i in range(len(points)):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def detect_plan_region(columns: List[ColumnHatch], margin: float = 4000.0) -> Optional[List[float]]:
    """The plan is where the column hatches cluster. A loose duplicate copy of the
    plan elsewhere in the file forms its own, smaller cluster and is ignored."""
    if not columns:
        return None
    centres = [((c.bbox[0] + c.bbox[2]) / 2, (c.bbox[1] + c.bbox[3]) / 2) for c in columns]
    best = max(_clusters(centres, link=15000.0), key=len)
    xs = [v for i in best for v in (columns[i].bbox[0], columns[i].bbox[2])]
    ys = [v for i in best for v in (columns[i].bbox[1], columns[i].bbox[3])]
    return [min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin]


def extract_entities(doc, cfg: StructuralConfig) -> RawEntities:
    msp = doc.modelspace()
    out = RawEntities()

    # ---- column / wall hatches (whole file; the plan region is derived from them)
    all_cols: List[ColumnHatch] = []
    for h in msp.query("HATCH"):
        if h.dxf.layer not in cfg.column_hatch_layers:
            continue
        polys = _hatch_polys(h)
        if not polys:
            continue
        xs = [x for pl in polys for x, _ in pl]
        ys = [y for pl in polys for _, y in pl]
        aci = h.dxf.get("color", 256)
        if aci in cfg.floating_column_aci:
            kind = "floating column"
        elif aci in cfg.hanging_column_aci:
            kind = "hanging"
        else:
            kind = "column/wall"
        all_cols.append(ColumnHatch(bbox=[min(xs), min(ys), max(xs), max(ys)], polys=polys, kind=kind, aci=aci))

    region = cfg.plan_region or detect_plan_region(all_cols)
    out.region = region

    def inbox(x: float, y: float) -> bool:
        return region is None or (region[0] <= x <= region[2] and region[1] <= y <= region[3])

    out.columns = [c for c in all_cols
                   if inbox((c.bbox[0] + c.bbox[2]) / 2, (c.bbox[1] + c.bbox[3]) / 2)]
    if len(all_cols) != len(out.columns):
        out.notes.append(f"{len(all_cols) - len(out.columns)} column hatch(es) outside the plan region ignored "
                         "(loose duplicate copy of the plan)")

    # ---- lines and arcs on the beam / slab layers, inside the region
    geo_layers = set(cfg.beam_line_layers) | set(cfg.slab_line_layers)
    for e in msp:
        t = e.dxftype()
        layer = e.dxf.layer
        if layer not in geo_layers:
            continue
        aci = e.dxf.get("color", 256)
        if t == "LINE":
            a = (e.dxf.start.x, e.dxf.start.y)
            b = (e.dxf.end.x, e.dxf.end.y)
            if inbox(*a) or inbox(*b):
                out.prims.append(Prim(kind="line", layer=layer, aci=aci, a=a, b=b))
        elif t == "LWPOLYLINE":
            pts = list(e.get_points("xyb"))
            if e.closed and pts:
                pts = pts + [pts[0]]
            for (x1, y1, bulge), (x2, y2, _b2) in zip(pts, pts[1:]):
                if abs(bulge) < 1e-9:
                    if inbox(x1, y1) or inbox(x2, y2):
                        out.prims.append(Prim(kind="line", layer=layer, aci=aci, a=(x1, y1), b=(x2, y2)))
                else:
                    try:
                        from ezdxf.math import bulge_to_arc
                        c, sa, ea, r = bulge_to_arc(Vec2(x1, y1), Vec2(x2, y2), bulge)
                        if inbox(c.x, c.y) or inbox(x1, y1):
                            out.prims.append(Prim(kind="arc", layer=layer, aci=aci, c=(c.x, c.y), r=r,
                                                  sa=math.degrees(sa), ea=math.degrees(ea)))
                    except Exception:  # noqa: BLE001
                        if inbox(x1, y1) or inbox(x2, y2):
                            out.prims.append(Prim(kind="line", layer=layer, aci=aci, a=(x1, y1), b=(x2, y2)))
        elif t == "ARC":
            c = e.dxf.center
            sp = e.start_point
            if inbox(sp.x, sp.y) or inbox(c.x, c.y):
                out.prims.append(Prim(kind="arc", layer=layer, aci=aci, c=(c.x, c.y), r=e.dxf.radius,
                                      sa=e.dxf.start_angle, ea=e.dxf.end_angle))

    # ---- all text (the schedule lives outside the plan region, so keep everything)
    for e in msp.query("TEXT MTEXT"):
        try:
            text = (e.dxf.text if e.dxftype() == "TEXT" else e.plain_text()).strip()
        except Exception:  # noqa: BLE001
            continue
        if not text:
            continue
        p = e.dxf.insert
        cx, cy, rot, h = _text_centre(e, text)
        out.texts.append(TextItem(text=text, layer=e.dxf.layer, x=p.x, y=p.y, cx=cx, cy=cy, rot=rot, h=h))

    return out
