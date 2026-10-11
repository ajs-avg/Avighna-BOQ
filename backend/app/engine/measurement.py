"""Measurement engine: elements read from drawings -> measurement sheet blocks (IS 1200 rules)
-> BOQ abstract (one line per item) -> material requirement (qty x norm x wastage).

Every quantity is a visible row: Nos x L x B x H, deductions as negative rows, rule in Remarks.
"""
from __future__ import annotations

import math
import re
from collections import OrderedDict
from typing import Dict, List, Optional, Sequence, Tuple

from app.models.schemas import (
    MaterialTotal, RoomBreakdown, RoomItemLine, RoomMiscLine, RoomOpeningLine,
    BOQAbstractLine, MaterialRow, MeasurementBlock, MeasurementExtraction, MeasurementResult, MeasurementRow,
    OpeningEl, ProjectAssumptions, RoomEl,
)

TRADE_ORDER = ["RCC", "Masonry", "Plaster", "Flooring", "Wall tiles", "Painting", "Waterproofing",
               "Doors & Windows", "Joinery", "Plumbing", "Electrical", "Sanitary", "Miscellaneous"]

# Steel densities when no BBS is available (guide: thumb rules, kg per cum of concrete)
STEEL_DENSITY = {"wall": 125.0, "column": 200.0, "beam": 150.0, "slab": 85.0}

# Material norms: item code prefix -> [(material, norm per BOQ unit, material unit, wastage %, basis)]
DEFAULT_NORMS: Dict[str, List[Tuple[str, float, str, float, str]]] = {
    "RCC": [("Ready-mix concrete", 1.0, "cum", 2.0, "RMC delivered; 2% wastage")],
    "STEEL": [("TMT bars Fe500D", 1.0, "kg", 3.0, "cutting waste 2-5%"),
              ("Binding wire", 0.009, "kg", 0.0, "~9 kg per MT of steel")],
    "FW": [("Shuttering oil", 0.08, "litre", 0.0, "per sqm contact area")],
    "BLOCK-CUM": [("AAC blocks 600x200x200", 41.7, "nos", 3.0, "1 cum = 41.7 blocks"),
                  ("Cement (mortar 1:4)", 1.2, "bags", 3.0, "per cum of wall"),
                  ("Sand (mortar)", 0.15, "cum", 5.0, "per cum of wall")],
    "BLOCK-SQM": [("AAC blocks 600x200x150", 8.3, "nos", 3.0, "guide: 8.3 nos per sqm"),
                  ("Cement (mortar 1:4)", 0.18, "bags", 3.0, "per sqm of half-block wall"),
                  ("Sand (mortar)", 0.022, "cum", 5.0, "")],
    "PLASTER-INT": [("Cement", 0.105, "bags", 3.0, "guide Ch.12: 12 mm 1:4 = 0.105 bag/sqm"),
                    ("Sand", 0.0144, "cum", 5.0, "guide Ch.12: 0.0144 cum/sqm")],
    "PLASTER-CLG": [("Cement", 0.065, "bags", 3.0, "6 mm 1:3"), ("Sand", 0.0075, "cum", 5.0, "")],
    "FLOOR": [("Floor tiles / stone", 1.0, "sqm", 7.0, "5-10% cutting waste"),
              ("Cement (20 mm bed 1:4)", 0.16, "bags", 3.0, ""),
              ("Sand (bed)", 0.021, "cum", 5.0, ""),
              ("Tile adhesive / grout", 0.5, "kg", 5.0, "")],
    "SKIRT": [("Skirting strips (600 mm)", 1.67, "nos", 7.0, "100 mm high strips")],
    "DADO": [("Wall tiles", 1.0, "sqm", 7.0, ""), ("Tile adhesive", 4.0, "kg", 5.0, "")],
    "PAINT": [("Wall putty", 1.2, "kg", 5.0, "2 coats"), ("Primer", 0.08, "litre", 5.0, "1 coat"),
              ("Interior emulsion", 0.12, "litre", 5.0, "2 coats")],
    "WP": [("Waterproofing compound / membrane", 1.0, "sqm", 5.0, "incl. 300 mm upturn")],
    "DOOR": [("Door set with frame & hardware", 1.0, "nos", 0.0, "")],
    "WIN": [("Aluminium window, fabricated to size", 1.0, "sqm", 0.0, "")],
}


def r3(v: float) -> float:
    return round(v + 1e-12, 3)


_SEQ = [0]


class _Block:
    def __init__(self, code: str, title: str, unit: str, trade: str, basis: str = "measured"):
        self.code, self.title, self.unit, self.trade, self.basis = code, title, unit, trade, basis
        self.rows: List[MeasurementRow] = []
        _SEQ[0] += 1
        self.seq = _SEQ[0]

    def add(self, location: str, nos: float, l: Optional[float], b: Optional[float], h: Optional[float],
            rule: str = "", element_id: Optional[str] = None, qty: Optional[float] = None,
            room_id: Optional[str] = None) -> None:
        if qty is None:
            qty = nos
            for v in (l, b, h):
                if v is not None:
                    qty *= v
        self.rows.append(MeasurementRow(sr=len(self.rows) + 1, location=location, nos=nos, l_m=l, b_m=b, h_m=h,
                                        qty=r3(qty), deduction=qty < 0, rule=rule, element_id=element_id,
                                        room_id=room_id))

    def total(self) -> float:
        return r3(sum(r.qty for r in self.rows))

    def to_model(self) -> MeasurementBlock:
        return MeasurementBlock(item_code=self.code, item_title=self.title, unit=self.unit, trade=self.trade,
                                rows=self.rows, total=self.total())


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _match_rooms(openings: Sequence[OpeningEl], rooms: Sequence[RoomEl]) -> Dict[str, Dict[str, float]]:
    """opening.id -> {room.id: count share}. Exact room name wins; otherwise the opening's room text is
    split on , & / ; and each part matches a room by substring (singular/plural tolerant), so a door
    schedule line "D06 - BOARDROOM, BOOTH, OFFICES x6" lands in every matching room. A count shared by
    several rooms is split as evenly as possible in whole numbers, remainder to the first rooms."""
    out: Dict[str, Dict[str, float]] = {}
    for o in openings:
        if not o.room:
            continue
        key = _norm(o.room)
        cands = [r for r in rooms if not r.level or not o.level or _norm(o.level) == _norm(r.level)]
        matched = [r for r in cands if _norm(r.name) == key]
        if not matched:
            parts = [x.strip() for x in re.split(r"[,&/;+]|\band\b", key) if x.strip()]
            for r in cands:
                rk = _norm(r.name)
                for part in parts:
                    ps = part.rstrip("s")
                    if part == rk or part in rk or rk in part or (len(ps) >= 4 and ps in rk):
                        matched.append(r)
                        break
        if not matched:
            continue
        n = len(matched)
        if o.count == int(o.count):
            whole = int(o.count)
            base, rem = whole // n, whole - (whole // n) * n
            shares = {r.id: float(base + (1 if i < rem else 0)) for i, r in enumerate(matched)}
        else:
            shares = {r.id: o.count / n for r in matched}
        out[o.id] = {rid: c for rid, c in shares.items() if c > 0}
    return out


def _find_room(text: str, rooms: Sequence[RoomEl], level: str = "") -> Optional[RoomEl]:
    """Single room referenced by free text ('PANTRY', 'Living Room'); None when ambiguous or unknown."""
    key = _norm(text)
    if not key or key in ("various", "all", "common", "general", "-"):
        return None
    cands = [r for r in rooms if not r.level or not level or _norm(level) == _norm(r.level)]
    exact = [r for r in cands if _norm(r.name) == key]
    if len(exact) == 1:
        return exact[0]
    part = [r for r in cands if key in _norm(r.name) or _norm(r.name) in key]
    return part[0] if len(part) == 1 else None


def _room_openings(room: RoomEl, openings: Sequence[OpeningEl], shares: Dict[str, Dict[str, float]]) -> List[OpeningEl]:
    out: List[OpeningEl] = []
    for o in openings:
        c = shares.get(o.id, {}).get(room.id)
        if c:
            out.append(o.model_copy(update={"count": c}))
    return out


def _opening_label(o: OpeningEl) -> str:
    return f"{o.kind.title()} {o.tag} ({o.width_m:.2f} x {o.height_m:.2f} m)"


def _plaster_deduction_rule(area: float) -> Tuple[int, str]:
    """IS 1200 Part 12: returns (faces to deduct, rule text)."""
    if area <= 0.5:
        return 0, "<= 0.5 sqm: no deduction (IS 1200 Pt 12)"
    if area <= 3.0:
        return 1, "0.5-3 sqm: deduct one face only, jambs not measured (IS 1200 Pt 12)"
    return 2, "> 3 sqm: deduct both faces, jambs/sill/soffit added (IS 1200 Pt 12)"


def compute_measurement(ex: MeasurementExtraction, norms: Optional[Dict[str, list]] = None) -> MeasurementResult:
    a: ProjectAssumptions = ex.assumptions
    blocks: "OrderedDict[str, _Block]" = OrderedDict()
    warnings: List[str] = list(ex.warnings)

    def blk(code: str, title: str, unit: str, trade: str, basis: str = "measured") -> _Block:
        if code not in blocks:
            blocks[code] = _Block(code, title, unit, trade, basis)
        return blocks[code]

    def loc(prefix: str, room: str = "", level: str = "") -> str:
        parts = [prefix] + [p for p in (room, level) if p]
        return ", ".join(parts)

    # ------------------------------------------------------------------ RCC walls
    concrete_by_type: Dict[str, float] = {"wall": 0.0, "column": 0.0, "beam": 0.0, "slab": 0.0}
    used_openings: set = set()
    for w in ex.walls:
        thk_mm = int(round(w.thickness_m * 1000))
        wall_openings = [o for o in ex.openings if o.wall_tag and _norm(o.wall_tag) == _norm(w.tag)]
        if w.wall_type == "rcc":
            c = blk("RCC-WALL", f"RCC {a.concrete_grade} in {'Mivan ' if a.construction == 'mivan' else ''}walls {thk_mm} mm thick, "
                    "including pumping, vibrating and curing (excl. steel and formwork)", "cum", "RCC")
            c.add(loc(f"Wall {w.tag}", w.room, w.level), w.count, w.length_m, w.thickness_m, w.height_m, "IS 1200 Pt 2", w.id)
            f = blk("FW-WALL", "Aluminium / plywood formwork (shuttering) to RCC walls, both faces, incl. fixing, propping and removal",
                    "sqm", "RCC")
            faces = 2 if w.both_faces else 1
            f.add(loc(f"Wall {w.tag}, {faces} face(s)", w.room, w.level), w.count * faces, w.length_m, None, w.height_m,
                  "contact area (IS 1200 Pt 5)", w.id)
            for o in wall_openings:
                used_openings.add(o.id)
                c.add(f"Deduct: {_opening_label(o)} in {w.tag}", -o.count, o.width_m, w.thickness_m, o.height_m, "opening > 0.1 sqm deducted", o.id)
                f.add(f"Deduct: {_opening_label(o)} in {w.tag}, {faces} face(s)", -o.count * faces, o.width_m, None, o.height_m, "", o.id)
            concrete_by_type["wall"] += c.rows[-1].qty if not wall_openings else 0  # recomputed below
        elif w.wall_type in ("block", "partition"):
            if w.thickness_m >= 0.2:
                m = blk("BLOCK-CUM", f"AAC / concrete block masonry {thk_mm} mm thick in cement mortar 1:4, incl. scaffolding and curing",
                        "cum", "Masonry")
                m.add(loc(f"Wall {w.tag}", w.room, w.level), w.count, w.length_m, w.thickness_m, w.height_m, "IS 1200 Pt 3", w.id)
                for o in wall_openings:
                    used_openings.add(o.id)
                    m.add(f"Deduct: {_opening_label(o)} in {w.tag}", -o.count, o.width_m, w.thickness_m, o.height_m, "all openings deducted (Pt 3)", o.id)
            else:
                m = blk("BLOCK-SQM", f"AAC / concrete block masonry {thk_mm} mm thick (half block) in cement mortar 1:4, incl. scaffolding",
                        "sqm", "Masonry")
                m.add(loc(f"Wall {w.tag}", w.room, w.level), w.count, w.length_m, None, w.height_m, "IS 1200 Pt 3 (half-block walls in sqm)", w.id)
                for o in wall_openings:
                    used_openings.add(o.id)
                    m.add(f"Deduct: {_opening_label(o)} in {w.tag}", -o.count, o.width_m, None, o.height_m, "all openings deducted", o.id)
    # recompute wall concrete total for steel
    if "RCC-WALL" in blocks:
        concrete_by_type["wall"] = blocks["RCC-WALL"].total()

    # ------------------------------------------------------------------ slabs, columns, beams
    for s in ex.slabs:
        thk_mm = int(round(s.thickness_m * 1000))
        c = blk("RCC-SLAB", f"RCC {a.concrete_grade} in slabs {thk_mm} mm thick, incl. pumping, vibrating and curing (excl. steel and formwork)", "cum", "RCC")
        c.add(loc(f"Slab {s.tag} ({s.length_m:.2f} x {s.width_m:.2f})", "", s.level), s.count, s.length_m, s.width_m, s.thickness_m, "measured over beams (IS 1200 Pt 2)", s.id)
        f = blk("FW-SLAB", "Formwork to slab soffit incl. props and de-shuttering", "sqm", "RCC")
        f.add(loc(f"Slab {s.tag} soffit between beams", "", s.level), s.count, max(s.length_m - s.beam_width_m, 0), max(s.width_m - s.beam_width_m, 0), None,
              "soffit only, beam widths excluded (Pt 5)", s.id)
    for m in ex.members:
        if m.kind == "column":
            c = blk("RCC-COL", f"RCC {a.concrete_grade} in columns, incl. pumping, vibrating and curing (excl. steel and formwork)", "cum", "RCC")
            c.add(loc(f"Column {m.tag} ({int(m.width_m*1000)} x {int(m.depth_m*1000)})", "", m.level), m.count, m.width_m, m.depth_m, m.length_m,
                  "floor top to slab soffit (Pt 2)", m.id)
            f = blk("FW-COL", "Formwork to columns, all four sides", "sqm", "RCC")
            f.add(loc(f"Column {m.tag}, perimeter x height", "", m.level), m.count, 2 * (m.width_m + m.depth_m), None, m.length_m, "4 sides (Pt 5)", m.id)
        else:
            d = max(m.depth_m - m.slab_thickness_m, 0.05)
            c = blk("RCC-BEAM", f"RCC {a.concrete_grade} in beams, incl. pumping, vibrating and curing (excl. steel and formwork)", "cum", "RCC")
            c.add(loc(f"Beam {m.tag} ({int(m.width_m*1000)} x {int(d*1000)} below slab)", "", m.level), m.count, m.width_m, d, m.length_m,
                  "depth below slab, clear span (Pt 2)", m.id)
            f = blk("FW-BEAM", "Formwork to beams, two sides and soffit", "sqm", "RCC")
            f.add(loc(f"Beam {m.tag}, (2 x depth + width) x span", "", m.level), m.count, 2 * d + m.width_m, None, m.length_m, "2 sides + soffit, top open (Pt 5)", m.id)
    for key, code in (("slab", "RCC-SLAB"), ("column", "RCC-COL"), ("beam", "RCC-BEAM")):
        if code in blocks:
            concrete_by_type[key] = blocks[code].total()
    if any(v > 0 for v in concrete_by_type.values()):
        st = blk("STEEL", "TMT reinforcement Fe500D, cut, bent and placed incl. binding wire (THUMB RULE until bar bending schedule is available)",
                 "kg", "RCC", basis="thumb_rule")
        for key, cum in concrete_by_type.items():
            if cum > 0:
                st.add(f"{key.title()}s: {cum:.3f} cum x {STEEL_DENSITY[key]:.0f} kg/cum", 1, None, None, None,
                       "thumb rule (guide Ch.11) - replace with BBS", qty=cum * STEEL_DENSITY[key])
        warnings.append("Steel is a thumb-rule estimate (kg per cum); replace with the bar bending schedule for tender BOQ.")

    # ------------------------------------------------------------------ rooms: finishes
    room_shares = _match_rooms(ex.openings, ex.rooms)
    for o in ex.openings:
        if o.room and o.id not in room_shares and not o.wall_tag:
            warnings.append(f"{o.kind.title()} {o.tag}: room '{o.room}' not found among the rooms, so no plaster/paint/skirting deduction was made for it")
    for room in ex.rooms:
        area = room.area_m2 if room.area_m2 else room.length_m * room.width_m
        perim = room.perimeter_m if room.perimeter_m else 2 * (room.length_m + room.width_m)
        H = room.height_m or a.floor_height_m
        ops = _room_openings(room, ex.openings, room_shares)
        where = loc(room.name, "", room.level)
        size_lbl = f"{room.length_m:.2f} x {room.width_m:.2f}" if not room.area_m2 else f"measured {area:.2f} sqm"

        # flooring per finish
        fcode = "FLOOR-" + _norm(room.floor_finish).replace(" ", "-")[:40]
        fl = blk(fcode, f"Providing and laying {room.floor_finish}, on cement mortar bed, incl. grouting, cleaning and curing", "sqm", "Flooring")
        if room.area_m2:
            fl.add(f"{where} floor ({size_lbl})", 1, None, None, None, "net between walls (IS 1200 Pt 11)", room.id, qty=area, room_id=room.id)
        else:
            fl.add(f"{where} floor", 1, room.length_m, room.width_m, None, "net between walls (IS 1200 Pt 11)", room.id, room_id=room.id)

        # skirting
        if room.skirting_mm > 0:
            sk = blk("SKIRT", f"Providing and fixing skirting {int(room.skirting_mm)} mm high to match flooring", "rmt", "Flooring")
            sk.add(f"{where} perimeter", 1, perim, None, None, "2 x (L + B)" if not room.perimeter_m else "measured perimeter", room.id, room_id=room.id)
            for o in ops:
                if o.kind in ("door", "opening"):
                    sk.add(f"Deduct: {_opening_label(o)} width", -o.count, o.width_m, None, None, "no skirting across doors", o.id, room_id=room.id)

        # wall plaster / paint base
        gross_wall = perim * H
        if room.plastered:
            pl = blk("PLASTER-INT", "Providing and applying 12 mm thick cement plaster 1:4 on internal walls, incl. scaffolding and curing", "sqm", "Plaster")
            pl.add(f"{where} walls, perimeter x height", 1, perim, None, H, "gross (IS 1200 Pt 12)", room.id, room_id=room.id)
            for o in ops:
                oa = o.width_m * o.height_m
                faces, rule = _plaster_deduction_rule(oa)
                if faces:
                    pl.add(f"Deduct: {_opening_label(o)}", -o.count * faces, o.width_m, None, o.height_m, rule, o.id, room_id=room.id)
                if faces == 2:
                    pl.add(f"Add: jambs, sill & soffit of {o.tag}", o.count, 2 * o.height_m + o.width_m, a.wall_thickness_m, None, "reveals measured (Pt 12)", o.id, room_id=room.id)
            cl = blk("PLASTER-CLG", "Providing and applying 6 mm thick cement plaster 1:3 on ceilings, incl. scaffolding and curing", "sqm", "Plaster")
            cl.add(f"{where} ceiling", 1, None if room.area_m2 else room.length_m, None if room.area_m2 else room.width_m, None, "ceiling separate item", room.id,
                   qty=area if room.area_m2 else None, room_id=room.id)
        # painting walls (same deductions as plaster rule)
        wf = room.wall_finish if re.search(r"putty|primer", room.wall_finish, re.I) else f"wall putty 2 coats + primer + {room.wall_finish}"
        pw = blk("PAINT-WALL", f"Providing and applying {wf} on internal walls", "sqm", "Painting") \
            if "tile" not in _norm(room.wall_finish) else None
        if pw is not None:
            pw.add(f"{where} walls, perimeter x height", 1, perim, None, H, "painted area = plastered area (Pt 13)", room.id, room_id=room.id)
            for o in ops:
                oa = o.width_m * o.height_m
                faces, rule = _plaster_deduction_rule(oa)
                if faces:
                    pw.add(f"Deduct: {_opening_label(o)}", -o.count * faces, o.width_m, None, o.height_m, rule, o.id, room_id=room.id)
            if room.dado_height_m > 0:
                pw.add(f"Deduct: dado zone {room.dado_height_m:.2f} m high", -1, perim, None, room.dado_height_m, "tiled zone not painted", room.id, room_id=room.id)
        cf = room.ceiling_finish if re.search(r"putty|primer", room.ceiling_finish, re.I) else f"putty + primer + {room.ceiling_finish}"
        pc = blk("PAINT-CLG", f"Providing and applying {cf} on ceilings", "sqm", "Painting")
        if room.area_m2:
            pc.add(f"{where} ceiling", 1, None, None, None, "", room.id, qty=area, room_id=room.id)
        else:
            pc.add(f"{where} ceiling", 1, room.length_m, room.width_m, None, "", room.id, room_id=room.id)

        # dado
        if room.dado_height_m > 0:
            dd = blk("DADO", f"Ceramic / vitrified wall tiles (dado) up to {room.dado_height_m:.2f} m height, incl. adhesive and grouting", "sqm", "Wall tiles")
            dd.add(f"{where} walls, perimeter x dado height", 1, perim, None, room.dado_height_m, "IS 1200 Pt 11", room.id, room_id=room.id)
            for o in ops:
                hh = min(o.height_m, room.dado_height_m)
                dd.add(f"Deduct: {_opening_label(o)} within dado", -o.count, o.width_m, None, hh, "", o.id, room_id=room.id)

        # waterproofing
        if room.wet_area:
            wp = blk("WP", "Waterproofing treatment to wet areas (floor + 300 mm upturn) with approved system", "sqm", "Waterproofing")
            wp.add(f"{where} floor", 1, None, None, None, "", room.id, qty=area, room_id=room.id)
            wp.add(f"{where} upturn 300 mm on perimeter", 1, perim, None, 0.3, "", room.id, room_id=room.id)

    # ------------------------------------------------------------------ openings as items
    seen_tags: Dict[str, OpeningEl] = {}
    rooms_by_id = {r.id: r for r in ex.rooms}
    for o in ex.openings:
        shares = room_shares.get(o.id) or {}
        places = [(rooms_by_id[rid].name, cnt, rid) for rid, cnt in shares.items() if rid in rooms_by_id] or [(o.room, o.count, None)]
        if o.kind in ("door", "opening"):
            key = f"DOOR-{o.tag.upper()}"
            d = blk(key, f"Supplying and fixing door {o.tag} {o.width_m:.2f} x {o.height_m:.2f} m: {o.description or 'flush door with frame, hardware and polish'}, complete", "nos", "Doors & Windows")
            for where_name, cnt, rid in places:
                d.add(loc(f"{o.tag}", where_name, o.level), cnt, None, None, None, "door schedule", o.id, room_id=rid)
        elif o.kind in ("window", "ventilator"):
            key = f"WIN-{o.tag.upper()}"
            wn = blk(key, f"Providing and fixing {o.kind} {o.tag} {o.width_m:.2f} x {o.height_m:.2f} m: {o.description or 'powder-coated aluminium sliding window with glass and mesh'}", "sqm", "Doors & Windows")
            for where_name, cnt, rid in places:
                wn.add(loc(f"{o.tag}", where_name, o.level), cnt, o.width_m, None, o.height_m, "window schedule", o.id, room_id=rid)

    # ------------------------------------------------------------------ misc items (AI judgement)
    for i, m in enumerate(ex.misc, 1):
        code = f"MISC-{_norm(m.trade).replace(' ', '-')[:12]}-{i}"
        mb = blk(code, m.description, m.unit, m.trade or "Miscellaneous")
        mr = _find_room(m.room, ex.rooms, m.level)
        mb.add(loc(m.tag or m.description[:30], m.room, m.level), m.qty, None, None, None, "from drawing / schedule", m.id,
               room_id=mr.id if mr else None)

    # ------------------------------------------------------------------ assemble
    ordered = sorted(blocks.values(), key=lambda b: (TRADE_ORDER.index(b.trade) if b.trade in TRADE_ORDER else 99, b.seq))
    out_blocks = [b.to_model() for b in ordered]
    boq: List[BOQAbstractLine] = []
    totals_by_trade: Dict[str, Dict[str, float]] = {}
    for i, b in enumerate(ordered, 1):
        boq.append(BOQAbstractLine(item_no=i, item_code=b.code, trade=b.trade, description=b.title, unit=b.unit,
                                   qty=b.total(), basis=b.basis))  # type: ignore[arg-type]
        totals_by_trade.setdefault(b.trade, {})
        totals_by_trade[b.trade][b.unit] = r3(totals_by_trade[b.trade].get(b.unit, 0.0) + b.total())
    materials = compute_materials(boq, norms or DEFAULT_NORMS)
    for b in ordered:
        if b.total() <= 0 and b.basis == "measured":
            warnings.append(f"{b.code}: total is zero or negative - check deductions")
    rooms_bd, common_bd = build_room_breakdown(ex, out_blocks, room_shares, norms or DEFAULT_NORMS)
    return MeasurementResult(blocks=out_blocks, boq=boq, materials=materials, totals_by_trade=totals_by_trade, warnings=warnings,
                             room_breakdown=rooms_bd, common_breakdown=common_bd)


def _breakdown_from_rows(name: str, room: Optional[RoomEl], blocks: Sequence[MeasurementBlock], rid: Optional[str],
                         norms: Dict[str, list], a: ProjectAssumptions) -> RoomBreakdown:
    items: List[RoomItemLine] = []
    totals: Dict[str, Dict[str, float]] = {}
    for b in blocks:
        q = r3(sum(r.qty for r in b.rows if r.room_id == rid))
        if abs(q) < 1e-9:
            continue
        items.append(RoomItemLine(item_code=b.item_code, item_title=b.item_title, trade=b.trade, unit=b.unit, qty=q))
        totals.setdefault(b.trade, {})
        totals[b.trade][b.unit] = r3(totals[b.trade].get(b.unit, 0.0) + q)
    pseudo = [BOQAbstractLine(item_no=i, item_code=it.item_code, trade=it.trade, description=it.item_title, unit=it.unit,
                              qty=it.qty, basis="measured") for i, it in enumerate(items, 1)]  # type: ignore[arg-type]
    mats = compute_materials(pseudo, norms)
    mt = [MaterialTotal(material=k, required=r3(v[0]), unit=v[1]) for k, v in material_totals(mats).items()]
    if room is None:
        return RoomBreakdown(room_id=None, name=name, items=items, materials=mats, material_totals=mt, totals_by_trade=totals)
    area = room.area_m2 if room.area_m2 else r3(room.length_m * room.width_m)
    perim = room.perimeter_m if room.perimeter_m else r3(2 * (room.length_m + room.width_m))
    return RoomBreakdown(room_id=room.id, name=room.name, level=room.level, length_m=room.length_m, width_m=room.width_m,
                         height_m=room.height_m or a.floor_height_m, area_m2=r3(area), perimeter_m=r3(perim),
                         floor_finish=room.floor_finish, wall_finish=room.wall_finish, ceiling_finish=room.ceiling_finish,
                         wet_area=room.wet_area, items=items, materials=mats, material_totals=mt, totals_by_trade=totals)


def build_room_breakdown(ex: MeasurementExtraction, blocks: Sequence[MeasurementBlock],
                         room_shares: Dict[str, Dict[str, float]], norms: Dict[str, list]
                         ) -> Tuple[List[RoomBreakdown], Optional[RoomBreakdown]]:
    """Room-wise view: every measurement row carries a room_id, so a room's share of each item is the
    sum of its rows; what has no room (RCC, slabs, members, 'various' items) goes to the common section.
    Sum of all rooms + common equals the measurement-sheet totals exactly."""
    a = ex.assumptions
    out: List[RoomBreakdown] = []
    for room in ex.rooms:
        bd = _breakdown_from_rows(room.name, room, blocks, room.id, norms, a)
        for o in ex.openings:
            cnt = (room_shares.get(o.id) or {}).get(room.id)
            if cnt:
                bd.openings.append(RoomOpeningLine(tag=o.tag, kind=o.kind, width_m=o.width_m, height_m=o.height_m,
                                                   count=cnt, description=o.description or ""))
        for m in ex.misc:
            mr = _find_room(m.room, ex.rooms, m.level)
            if mr is not None and mr.id == room.id:
                bd.misc.append(RoomMiscLine(description=m.description, qty=m.qty, unit=m.unit, trade=m.trade or "Miscellaneous", tag=m.tag or ""))
        out.append(bd)
    common = _breakdown_from_rows("Common / whole floor", None, blocks, None, norms, a)
    for o in ex.openings:
        if not room_shares.get(o.id):
            common.openings.append(RoomOpeningLine(tag=o.tag, kind=o.kind, width_m=o.width_m, height_m=o.height_m,
                                                   count=o.count, description=o.description or ""))
    for m in ex.misc:
        if _find_room(m.room, ex.rooms, m.level) is None:
            common.misc.append(RoomMiscLine(description=m.description, qty=m.qty, unit=m.unit, trade=m.trade or "Miscellaneous", tag=m.tag or ""))
    if not (common.items or common.openings or common.misc):
        return out, None
    return out, common


def _norms_for(code: str, norms: Dict[str, list]) -> list:
    if code.startswith("RCC-"):
        return norms.get("RCC", [])
    if code.startswith("FW-"):
        return norms.get("FW", [])
    for prefix in ("STEEL", "BLOCK-CUM", "BLOCK-SQM", "PLASTER-INT", "PLASTER-CLG", "FLOOR", "SKIRT", "DADO", "PAINT", "WP", "DOOR", "WIN"):
        if code.startswith(prefix):
            return norms.get(prefix, [])
    return []


def compute_materials(boq: Sequence[BOQAbstractLine], norms: Dict[str, list]) -> List[MaterialRow]:
    rows: List[MaterialRow] = []
    agg: "OrderedDict[Tuple[str, str, str], MaterialRow]" = OrderedDict()
    for line in boq:
        if line.qty <= 0:
            continue
        for material, norm, munit, waste, basis in _norms_for(line.item_code, norms):
            req = line.qty * norm * (1 + waste / 100.0)
            rows.append(MaterialRow(material=material, for_item_code=line.item_code, boq_qty=line.qty, boq_unit=line.unit,
                                    norm=norm, norm_unit=munit, wastage_pct=waste, required=round(req, 2), basis=basis))
    return rows


def material_totals(materials: Sequence[MaterialRow]) -> Dict[str, Tuple[float, str]]:
    out: Dict[str, Tuple[float, str]] = {}
    for m in materials:
        q, u = out.get(m.material, (0.0, m.norm_unit))
        out[m.material] = (round(q + m.required, 2), u)
    return out
