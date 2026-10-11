"""Deterministic measurement facts for interior fit-out drawings.

From a DXF (converted DWG) we compute what a QS would measure by hand:
  - hatch areas (floor / wall / ceiling finish zones) with the finish code tagged on them
  - room polygons -> area, perimeter, with the room name found inside
  - counts of block references and attribute tags (fixtures, furniture, joinery callouts)
  - polyline lengths per layer (skirting, bulkheads, trims)
  - dimension values
From a PDF only text facts are available (codes + counts); areas come from the vision model.
These facts are given to the model with instruction to prefer them over estimates.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from app.extract.inventory import SheetInventory

CODE_RX = re.compile(r"\b([A-Z]{1,3})-(\d{2,3})([A-Z])?\b")          # FC-201, J-013, LI-501, CH-101, J-05A
ROOM_LAYER_RX = re.compile(r"room|area|space|zone", re.I)
ANNOTATION_BLOCK_RX = re.compile(r"anno|tag|title|detref|callout|north|scale|grid|\*u|\*x|sop|_|rev", re.I)
LENGTH_LAYER_RX = re.compile(r"skirt|trim|bulkhead|pelmet|cove|ceil|curtain|partition|wall", re.I)
INSUNITS_TO_M = {1: 0.0254, 2: 0.3048, 3: 1609.344, 4: 0.001, 5: 0.01, 6: 1.0, 14: 0.1}


@dataclass
class HatchFact:
    area_m2: float
    perimeter_m: float
    layer: str
    pattern: str
    code: Optional[str] = None
    code_source: str = ""
    room: Optional[str] = None
    cx: float = 0.0
    cy: float = 0.0


@dataclass
class RoomFact:
    name: str
    area_m2: float
    perimeter_m: float
    layer: str = ""


@dataclass
class MeasuredFacts:
    source: str
    units: str = "unknown"
    scale_to_m: float = 0.001
    hatches: List[HatchFact] = field(default_factory=list)
    rooms: List[RoomFact] = field(default_factory=list)
    block_counts: Dict[str, int] = field(default_factory=dict)
    attrib_counts: Dict[str, int] = field(default_factory=dict)
    code_counts: Dict[str, int] = field(default_factory=dict)
    length_by_layer_m: Dict[str, float] = field(default_factory=dict)
    dimensions: List[float] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def area_by_code(self) -> Dict[str, float]:
        out: Dict[str, float] = defaultdict(float)
        for h in self.hatches:
            if h.code:
                out[h.code] += h.area_m2
        return {k: round(v, 2) for k, v in out.items()}

    def rooms_by_code(self) -> Dict[str, List[str]]:
        out: Dict[str, set] = defaultdict(set)
        for h in self.hatches:
            if h.code and h.room:
                out[h.code].add(h.room)
        return {k: sorted(v) for k, v in out.items()}

    def is_empty(self) -> bool:
        return not (self.hatches or self.rooms or self.block_counts or self.attrib_counts or self.code_counts)

    def to_prompt_text(self, max_items: int = 60) -> str:
        if self.is_empty():
            return "(no geometry facts available for this sheet - measure from dimensions and notes)"
        d = {
            "units": self.units,
            "finish_area_m2_by_code": self.area_by_code(),
            "rooms_by_code": self.rooms_by_code(),
            "rooms": [asdict(r) for r in self.rooms[:max_items]],
            "hatches": [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in asdict(h).items() if k not in ("cx", "cy")}
                        for h in self.hatches[:max_items]],
            "block_counts": dict(sorted(self.block_counts.items(), key=lambda kv: -kv[1])[:max_items]),
            "tag_counts": dict(sorted(self.attrib_counts.items(), key=lambda kv: -kv[1])[:max_items]),
            "text_code_counts": dict(sorted(self.code_counts.items())[:max_items * 2]),
            "polyline_length_m_by_layer": {k: round(v, 2) for k, v in self.length_by_layer_m.items()},
            "dimension_values": self.dimensions[:80],
            "notes": self.notes,
        }
        return json.dumps(d, ensure_ascii=False)


# ----------------------------------------------------------------------------- geometry helpers
def _poly_area(pts: Sequence[Tuple[float, float]]) -> float:
    if len(pts) < 3:
        return 0.0
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def _poly_perimeter(pts: Sequence[Tuple[float, float]], closed: bool = True) -> float:
    n = len(pts)
    if n < 2:
        return 0.0
    total = 0.0
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        total += math.hypot(x1 - x0, y1 - y0)
    return total


def _centroid(pts: Sequence[Tuple[float, float]]) -> Tuple[float, float]:
    if not pts:
        return 0.0, 0.0
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def _point_in_poly(x: float, y: float, pts: Sequence[Tuple[float, float]]) -> bool:
    inside = False
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xint = x0 + (y - y0) * (x1 - x0) / ((y1 - y0) or 1e-12)
            if x < xint:
                inside = not inside
    return inside


def _flatten_path(path, distance: float) -> List[List[Tuple[float, float]]]:
    """ezdxf Path (possibly multi) -> list of closed vertex loops."""
    loops: List[List[Tuple[float, float]]] = []
    try:
        subs = list(path.sub_paths()) if getattr(path, "has_sub_paths", False) else [path]
    except Exception:
        subs = [path]
    for sp in subs:
        try:
            pts = [(float(v.x), float(v.y)) for v in sp.flattening(distance)]
        except Exception:
            continue
        if len(pts) >= 3:
            if abs(pts[0][0] - pts[-1][0]) < 1e-6 and abs(pts[0][1] - pts[-1][1]) < 1e-6:
                pts = pts[:-1]
            if len(pts) >= 3:
                loops.append(pts)
    return loops


def _hatch_loops(hatch, distance: float) -> List[List[Tuple[float, float]]]:
    loops: List[List[Tuple[float, float]]] = []
    try:
        from ezdxf.path import from_hatch
        result = from_hatch(hatch)
        paths = list(result) if hasattr(result, "__iter__") and not hasattr(result, "flattening") else [result]
        for p in paths:
            loops.extend(_flatten_path(p, distance))
        if loops:
            return loops
    except Exception:
        pass
    # fallback: polyline boundary paths only
    for bp in hatch.paths:
        try:
            if bp.type.name.lower().startswith("polyline"):
                pts = [(float(v[0]), float(v[1])) for v in bp.vertices]
                if len(pts) >= 3:
                    loops.append(pts)
        except Exception:
            continue
    return loops


def _even_odd_area(loops: List[List[Tuple[float, float]]]) -> Tuple[float, float, List[Tuple[float, float]]]:
    """Area with holes removed (even-odd nesting). Returns (area, outer perimeter, outer loop)."""
    if not loops:
        return 0.0, 0.0, []
    loops = sorted(loops, key=lambda l: -abs(_poly_area(l)))
    area = 0.0
    outer = loops[0]
    for i, lp in enumerate(loops):
        depth = 0
        cx, cy = lp[0]
        for j, other in enumerate(loops[:i]):
            if _point_in_poly(cx, cy, other):
                depth += 1
        a = abs(_poly_area(lp))
        area += a if depth % 2 == 0 else -a
    return max(area, 0.0), _poly_perimeter(outer), outer


# ----------------------------------------------------------------------------- DXF
def measure_dxf(path: Path, inv: Optional[SheetInventory] = None) -> MeasuredFacts:
    import ezdxf

    facts = MeasuredFacts(source=path.name)
    from app.extract.dxf_reader import load_dxf
    doc = load_dxf(path)
    units_code = int(doc.header.get("$INSUNITS", 0) or 0)
    scale = INSUNITS_TO_M.get(units_code)
    if scale is None:
        hint = (inv.units_hint if inv else "unknown")
        scale = {"mm": 0.001, "cm": 0.01, "m": 1.0}.get(hint, 0.001)
        facts.notes.append(f"$INSUNITS={units_code} unknown; assumed {hint or 'mm'}")
    facts.units = {0.001: "mm", 0.01: "cm", 1.0: "m"}.get(scale, str(scale))
    facts.scale_to_m = scale
    msp = doc.modelspace()
    flat_dist = 5.0 * (0.001 / scale)  # ~5 mm flattening tolerance

    # --- texts with positions (for tag <-> geometry association)
    texts: List[Tuple[str, float, float, str]] = []  # (text, x, y, layer)
    for e in msp:
        t = e.dxftype()
        try:
            if t == "TEXT":
                ins = e.dxf.insert
                texts.append((e.dxf.text.strip(), float(ins.x), float(ins.y), e.dxf.layer))
            elif t == "MTEXT":
                ins = e.dxf.insert
                for line in e.plain_text().split("\n"):
                    if line.strip():
                        texts.append((line.strip(), float(ins.x), float(ins.y), e.dxf.layer))
            elif t == "INSERT":
                name = e.dxf.name
                ins = e.dxf.insert
                for att in e.attribs:
                    val = (att.dxf.text or "").strip()
                    if val:
                        texts.append((val, float(ins.x), float(ins.y), att.dxf.layer))
                        facts.attrib_counts[val] = facts.attrib_counts.get(val, 0) + 1
                if not ANNOTATION_BLOCK_RX.search(name):
                    facts.block_counts[name] = facts.block_counts.get(name, 0) + 1
            elif t == "DIMENSION":
                try:
                    v = float(e.get_measurement())
                    if v > 0:
                        facts.dimensions.append(round(v * scale, 3))
                except Exception:
                    pass
        except Exception:
            continue
    code_texts = [(m.group(0), x, y) for (txt, x, y, _l) in texts for m in [CODE_RX.search(txt.upper())] if m]
    for c, _x, _y in code_texts:
        facts.code_counts[c] = facts.code_counts.get(c, 0) + 1
    _BAD_WORDS = re.compile(r"DESCRIPTION|LEGEND|SYMBOL|FINISH|NOTE|SCALE|PLAN|SECTION|ELEVATION|DETAIL|TYP|FFL|FCL|"
                            r"LEVEL|DRAWING|TITLE|PROJECT|CLIENT|DATE|REV|SHEET|AFFL|KEY|NORTH|GRID|LIGHT|OUTLET|SWITCH|SOCKET|"
                            r"CHAIR|TABLE|FRIDGE|SOFA|DESK|POWER|DATA|GRILLE|DIFFUSER|PANEL|SHELF|COUNTER|BENCH|STOOL|"
                            r"CUPBOARD|CABINET|MIRROR|BASIN|SINK|WC\b|TV\b|SCREEN|PRINTER|RUG\b|CARPET|STONE|TILE|TIMBER|"
                            r"GLASS|METAL|PAINT|VENEER|FABRIC|LAMINATE|WALLPAPER|SKIRTING|JOINERY|ACCESSOR|FURNITURE|LOOSE|FIXED|"
                            r"EQUIPMENT|APPLIANCE|SANITARY|IRONMONGERY|HARDWARE|LAMP|FIXTURE|PLANT|ARTWORK|SIGNAGE|DISPENSER|"
                            r"MACHINE|COFFEE|WATER|BIN\b|\d{3,}")
    attrib_values = set(facts.attrib_counts)
    _ANNO_LAYER = re.compile(r"anno|tag|legend|title|dim|leader|note|text-tag|sym", re.I)
    room_name_texts = [(txt, x, y) for (txt, x, y, layer) in texts
                       if txt.isupper() and 4 <= len(txt) <= 32 and not CODE_RX.search(txt) and txt not in attrib_values
                       and not _BAD_WORDS.search(txt) and re.match(r"^[A-Z][A-Z0-9 .'&/-]+$", txt)
                       and not _ANNO_LAYER.search(layer)]

    # --- room polygons: for every room name, the smallest closed polyline that contains it
    polylines = []
    for e in msp.query("LWPOLYLINE POLYLINE"):
        try:
            if e.dxftype() == "LWPOLYLINE":
                pts = [(float(p[0]), float(p[1])) for p in e.get_points("xy")]
                closed = bool(e.closed)
            else:
                pts = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in e.vertices]
                closed = bool(e.is_closed)
            if len(pts) >= 2:
                polylines.append((e.dxf.layer, pts, closed))
        except Exception:
            continue
    closed_polys = []
    for layer, pts, closed in polylines:
        length = _poly_perimeter(pts, closed) * scale
        if LENGTH_LAYER_RX.search(layer):
            facts.length_by_layer_m[layer] = round(facts.length_by_layer_m.get(layer, 0.0) + length, 3)
        if closed and len(pts) >= 3:
            area = abs(_poly_area(pts)) * scale * scale
            if 1.0 <= area <= 3000:
                closed_polys.append((layer, pts, area, length))
    room_layer_rx = re.compile(r"room|area|outline|zone|space|flr|floor", re.I)
    used = set()
    for name, x, y in room_name_texts:
        containing = [(i, lp) for i, lp in enumerate(closed_polys) if _point_in_poly(x, y, lp[1])]
        if not containing:
            continue
        preferred = [c for c in containing if room_layer_rx.search(c[1][0])] or containing
        i, (layer, pts, area, length) = min(preferred, key=lambda c: c[1][2])
        if i in used or any(r.name == name and abs(r.area_m2 - area) < 0.05 for r in facts.rooms):
            continue
        used.add(i)
        facts.rooms.append(RoomFact(name=name, area_m2=round(area, 2), perimeter_m=round(length, 2), layer=layer))

    # --- leaders link a tag text (tail) to the zone it points at (arrow head)
    leaders: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []  # (arrow_xy, tail_xy)
    for e in msp.query("LEADER"):
        try:
            vs = [(float(v[0]), float(v[1])) for v in e.vertices]
            if len(vs) >= 2:
                leaders.append((vs[0], vs[-1]))
        except Exception:
            continue
    for e in msp.query("MLEADER MULTILEADER"):
        try:
            ctx = e.context
            for ld in ctx.leaders:
                for ln in ld.lines:
                    vs = [(float(v.x), float(v.y)) for v in ln.vertices]
                    if vs:
                        leaders.append((vs[0], (float(ctx.base_point.x), float(ctx.base_point.y))))
        except Exception:
            continue
    _SKIP_HATCH_LAYER = re.compile(r"sow|scope|bound|revis|hatch-wall|wall-hatch|clad|col|pdf_", re.I)

    # --- hatches
    hatch_rows: List[Tuple[HatchFact, List[Tuple[float, float]]]] = []
    for h in msp.query("HATCH"):
        if _SKIP_HATCH_LAYER.search(h.dxf.layer):
            continue
        try:
            loops = _hatch_loops(h, flat_dist)
            area_u, perim_u, outer = _even_odd_area(loops)
            area = area_u * scale * scale
            if area <= 0.01:
                continue
            cx, cy = _centroid(outer)
            hf = HatchFact(area_m2=round(area, 3), perimeter_m=round(perim_u * scale, 3), layer=h.dxf.layer,
                           pattern=getattr(h.dxf, "pattern_name", "") or "", cx=cx, cy=cy)
            # finish code: a code text inside the hatch wins, else the nearest code text
            inside = [c for (c, x, y) in code_texts if _point_in_poly(x, y, outer)]
            if inside:
                hf.code, hf.code_source = Counter(inside).most_common(1)[0][0], "tag inside hatch"
            elif code_texts:
                c, dist = min(((c, math.hypot(x - cx, y - cy)) for (c, x, y) in code_texts), key=lambda kv: kv[1])
                if dist * scale < 6.0:  # within 6 m of the centroid
                    hf.code, hf.code_source = c, f"nearest tag ({dist * scale:.1f} m)"
            if not hf.code and leaders and code_texts:
                # a leader whose arrow lands inside this hatch; its tail sits next to a tag text
                best = None
                for arrow, tail in leaders:
                    if _point_in_poly(arrow[0], arrow[1], outer):
                        c, dist = min(((c, math.hypot(x - tail[0], y - tail[1])) for (c, x, y) in code_texts), key=lambda kv: kv[1])
                        if dist * scale < 4.0 and (best is None or dist < best[1]):
                            best = (c, dist)
                if best:
                    hf.code, hf.code_source = best[0], "leader from tag"
            rooms_in = [n for (n, x, y) in room_name_texts if _point_in_poly(x, y, outer)]
            if rooms_in:
                hf.room = rooms_in[0]
            hatch_rows.append((hf, outer))
        except Exception as exc:
            facts.notes.append(f"hatch skipped: {exc}")
    # drop duplicate hatches (same zone drawn twice with different patterns) and
    # let untagged hatches inherit the code of a tagged hatch drawn in the same style
    kept: List[HatchFact] = []
    for hf, outer in hatch_rows:
        dup = next((k for k in kept if k.room == hf.room and abs(k.area_m2 - hf.area_m2) <= 0.03 * max(k.area_m2, 0.01)
                    and math.hypot(k.cx - hf.cx, k.cy - hf.cy) * scale < 1.0), None)
        if dup:
            if not dup.code and hf.code:
                dup.code, dup.code_source = hf.code, hf.code_source
            continue
        kept.append(hf)
    style_code: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
    for k in kept:
        if k.code:
            style_code[(k.layer, k.pattern)][k.code] += 1
    for k in kept:
        if not k.code and (k.layer, k.pattern) in style_code:
            k.code, k.code_source = style_code[(k.layer, k.pattern)].most_common(1)[0][0], "same hatch style as tagged zone"
    facts.hatches = kept
    for r in facts.rooms:
        inside = [k for k in kept if k.room == r.name]
        if inside:
            hatch_area = max(k.area_m2 for k in inside)
            if r.area_m2 > 2.0 * hatch_area:
                best = max(inside, key=lambda k: k.area_m2)
                facts.notes.append(f"room {r.name}: outline {r.area_m2:.1f} m2 replaced by finish zone {best.area_m2:.1f} m2")
                r.area_m2, r.perimeter_m = best.area_m2, best.perimeter_m
    untagged = [k for k in kept if not k.code]
    if untagged:
        facts.notes.append(f"{len(untagged)} hatch zone(s) without a finish code: " +
                           ", ".join(f"{k.room or k.layer} {k.area_m2:.1f} m2 [{k.layer}/{k.pattern}]" for k in untagged[:10]))
    if not facts.hatches:
        facts.notes.append("no hatch areas in model space (finish zones may live in an xref not supplied)")
    xrefs = [b.name for b in doc.blocks if b.block.dxf.flags & 4]
    if xrefs:
        facts.notes.append("xrefs referenced but not resolved: " + ", ".join(xrefs[:8]))
    return facts


# ----------------------------------------------------------------------------- PDF / image (text only)
def measure_from_inventory(inv: SheetInventory) -> MeasuredFacts:
    facts = MeasuredFacts(source=f"{inv.source} p{inv.page_no}", units=inv.units_hint)
    for t in inv.texts:
        m = CODE_RX.search(t.text.upper())
        if m:
            facts.code_counts[m.group(0)] = facts.code_counts.get(m.group(0), 0) + 1
        if t.kind == "dimension":
            try:
                facts.dimensions.append(float(t.text))
            except ValueError:
                pass
    facts.notes.append("vector PDF: areas must be derived from dimension strings; code counts are text occurrences")
    return facts
