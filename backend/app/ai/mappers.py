"""Map the flat AI response models to the canonical schemas (mm -> m) and merge sheets."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.ai.prompts import (
    AIFitoutExtraction, AISheetClass, AISlabLayer, AIStructuralExtraction,
)
from app.models.schemas import (
    BarGroup, BeamSpec, ColumnSpec, ColumnTie, FitoutExtraction, FitoutItem, GeneralNotes, RoomRecord,
    SheetClassification, SlabLayer, SlabSpec, StairFlight, StairSpec, StirrupZone, StructuralExtraction,
    WallSpec,
)


def _m(v: Optional[float]) -> float:
    return round((v or 0.0) / 1000.0, 4)


def _groups(gs) -> List[BarGroup]:
    return [BarGroup(count=int(g.count), dia_mm=int(g.dia_mm)) for g in gs if g.count and g.dia_mm]


def _layer(l: Optional[AISlabLayer]) -> Optional[SlabLayer]:
    if l is None or not l.spacing_mm:
        return None
    return SlabLayer(dia_mm=int(l.dia_mm), spacing_mm=float(l.spacing_mm), bent_up=bool(l.bent_up))


def classification_from_ai(c: AISheetClass) -> SheetClassification:
    return SheetClassification(**c.model_dump())


def structural_from_ai(ai: AIStructuralExtraction, sheet_label: str) -> StructuralExtraction:
    out = StructuralExtraction(warnings=list(ai.warnings))
    for b in ai.beams:
        if b.span_mm <= 0 or b.width_mm <= 0 or b.depth_mm <= 0:
            out.warnings.append(f"Beam {b.tag}: incomplete size, skipped")
            continue
        out.beams.append(BeamSpec(
            tag=b.tag.strip(), nos=max(1, b.nos), span_m=_m(b.span_mm), width_m=_m(b.width_mm), depth_m=_m(b.depth_mm),
            bottom_bars=_groups(b.bottom_bars), top_bars=_groups(b.top_bars),
            extra_top_left=_groups(b.extra_top_left), extra_top_right=_groups(b.extra_top_right),
            extra_bottom_mid=_groups(b.extra_bottom_mid), bottom_curtail=_groups(b.bottom_curtail),
            sfr_bars=_groups(b.sfr_bars),
            stirrups=[StirrupZone(dia_mm=int(s.dia_mm), spacing_mm=float(s.spacing_mm), zone=s.zone, legs=max(2, s.legs))
                      for s in b.stirrups if s.spacing_mm],
            left_support=b.left_support, right_support=b.right_support,
            confidence=b.confidence, evidence=b.evidence, source_sheet=sheet_label, remarks=b.remarks,
        ))
    for s in ai.slabs:
        if s.short_span_mm <= 0 or s.long_span_mm <= 0 or s.thickness_mm <= 0:
            out.warnings.append(f"Slab {s.tag}: incomplete size, skipped")
            continue
        lx, ly = sorted([s.short_span_mm, s.long_span_mm])
        out.slabs.append(SlabSpec(
            tag=s.tag.strip(), nos=max(1, s.nos), length_m=_m(lx), width_m=_m(ly), thickness_m=_m(s.thickness_mm),
            short_main=_layer(s.short_main), long_main=_layer(s.long_main),
            short_top_dist_end=_layer(s.short_top_dist_end), long_top_dist_end=_layer(s.long_top_dist_end),
            short_top_cont_edge=_layer(s.short_top_cont_edge), long_top_cont_edge=_layer(s.long_top_cont_edge),
            one_way=s.one_way, confidence=s.confidence, evidence=s.evidence, source_sheet=sheet_label, remarks=s.remarks,
        ))
    for c in ai.columns:
        if c.length_mm <= 0 or c.width_mm <= 0 or c.height_mm <= 0:
            out.warnings.append(f"Column {c.tag}: incomplete size/height, skipped")
            continue
        out.columns.append(ColumnSpec(
            tag=c.tag.strip(), nos=max(1, c.nos), length_m=_m(c.length_mm), width_m=_m(c.width_mm), height_m=_m(c.height_mm),
            vertical_bars=_groups(c.vertical_bars),
            ties=[ColumnTie(dia_mm=int(t.dia_mm), spacing_mm=float(t.spacing_mm), kind=t.kind, per_layer=max(1, t.per_layer),
                            leg_length_m=_m(t.leg_length_mm) if t.leg_length_mm else None) for t in c.ties if t.spacing_mm],
            shape=c.shape, confidence=c.confidence, evidence=c.evidence, source_sheet=sheet_label, remarks=c.remarks,
        ))
    for w in ai.walls:
        if w.length_mm <= 0 or w.thickness_mm <= 0 or w.height_mm <= 0:
            out.warnings.append(f"Wall {w.tag}: incomplete size, skipped")
            continue
        out.walls.append(WallSpec(
            tag=w.tag.strip(), nos=max(1, w.nos), length_m=_m(w.length_mm), thickness_m=_m(w.thickness_mm), height_m=_m(w.height_mm),
            vertical=_layer(w.vertical), horizontal=_layer(w.horizontal), faces=2 if w.faces >= 2 else 1,
            confidence=w.confidence, evidence=w.evidence, source_sheet=sheet_label, remarks=w.remarks,
        ))
    for st in ai.stairs:
        flights = [StairFlight(name=f.name, width_m=_m(f.width_mm), waist_m=_m(f.waist_mm), going_m=_m(f.going_mm),
                               rise_m=_m(f.rise_mm), landing_a_m=_m(f.landing_a_mm), landing_b_m=_m(f.landing_b_mm),
                               main=_layer(f.main), dist=_layer(f.dist)) for f in st.flights if f.width_mm > 0]
        if not flights:
            out.warnings.append(f"Stair {st.tag}: no usable flights, skipped")
            continue
        out.stairs.append(StairSpec(tag=st.tag.strip(), nos=max(1, st.nos), flights=flights, confidence=st.confidence,
                                    evidence=st.evidence, source_sheet=sheet_label, remarks=st.remarks))
    gn = ai.general_notes
    out.general_notes = GeneralNotes(ld_factor=gn.ld_factor, cover_beam_mm=gn.cover_beam_mm, cover_slab_mm=gn.cover_slab_mm,
                                     cover_column_mm=gn.cover_column_mm, concrete_grade=gn.concrete_grade,
                                     steel_grade=gn.steel_grade, notes=list(gn.notes))
    return out


def merge_structural(parts: List[StructuralExtraction]) -> StructuralExtraction:
    """Union across sheets; the same tag on several sheets keeps the most confident reading."""
    out = StructuralExtraction()
    seen: Dict[Tuple[str, str], int] = {}
    for p in parts:
        out.warnings.extend(p.warnings)
        for attr in ("beams", "slabs", "columns", "walls", "stairs"):
            for m in getattr(p, attr):
                key = (attr, m.tag.upper())
                lst = getattr(out, attr)
                if key in seen:
                    old = lst[seen[key]]
                    if m.confidence > old.confidence:
                        m.evidence = list(dict.fromkeys(old.evidence + m.evidence))
                        lst[seen[key]] = m
                    else:
                        old.evidence = list(dict.fromkeys(old.evidence + m.evidence))
                else:
                    seen[key] = len(lst)
                    lst.append(m)
        gn, og = p.general_notes, out.general_notes
        for f in ("ld_factor", "cover_beam_mm", "cover_slab_mm", "cover_column_mm", "concrete_grade", "steel_grade"):
            if getattr(og, f) is None and getattr(gn, f) is not None:
                setattr(og, f, getattr(gn, f))
        og.notes = list(dict.fromkeys(og.notes + gn.notes))
    return out


# ----------------------------------------------------------------------------- fit-out
def fitout_from_ai(ai: AIFitoutExtraction, sheet_label: str) -> FitoutExtraction:
    out = FitoutExtraction(warnings=list(ai.warnings))
    for it in ai.items:
        if not it.description.strip():
            continue
        out.items.append(FitoutItem(
            division=it.division, section=it.section.strip() or "Other", code=(it.code or "").strip() or None,
            description=it.description.strip(), unit=it.unit, qty=max(0.0, float(it.qty or 0)), qty_basis=it.qty_basis,
            rooms=[r.strip() for r in it.rooms if r.strip()], size_label=it.size_label, specification=it.specification,
            confidence=it.confidence, evidence=it.evidence, source_sheet=sheet_label, remarks=it.remarks,
        ))
    for r in ai.rooms:
        if r.name.strip():
            out.rooms.append(RoomRecord(name=r.name.strip().upper(), area_m2=r.area_m2, perimeter_m=r.perimeter_m,
                                        ceiling_height_m=r.ceiling_height_m, floor_finish=r.floor_finish,
                                        wall_finishes=r.wall_finishes, ceiling_finish=r.ceiling_finish,
                                        source_sheet=sheet_label, confidence=r.confidence, evidence=r.evidence))
    for e in ai.legend:
        if e.code.strip():
            out.legend[e.code.strip().upper()] = e.description.strip()
    return out


def _item_key(it: FitoutItem) -> Tuple[str, str, str]:
    return (it.division, (it.code or it.description).strip().upper(), it.unit)


def merge_fitout(parts: List[FitoutExtraction]) -> FitoutExtraction:
    """Items with the same code+unit from different sheets describe the same thing: rooms are
    unioned; quantities are summed only when the room sets are disjoint, otherwise the larger
    reading is kept (an enlarged plan repeats the overall plan). Rooms merge by name."""
    out = FitoutExtraction()
    idx: Dict[Tuple[str, str, str], int] = {}
    for p in parts:
        out.warnings.extend(p.warnings)
        out.legend.update(p.legend)
        for it in p.items:
            key = _item_key(it)
            if key not in idx:
                idx[key] = len(out.items)
                out.items.append(it)
                continue
            cur = out.items[idx[key]]
            cur_rooms, new_rooms = {r.upper() for r in cur.rooms}, {r.upper() for r in it.rooms}
            disjoint = bool(cur_rooms) and bool(new_rooms) and not (cur_rooms & new_rooms)
            if disjoint:
                cur.qty = round(cur.qty + it.qty, 3)
            elif it.qty > cur.qty:
                if cur.qty > 0:
                    cur.remarks = ((cur.remarks or "") + f" | {it.source_sheet}: {it.qty} {it.unit} (kept larger of overlapping sheets)").strip(" |")
                cur.qty = it.qty
                cur.qty_basis = it.qty_basis
            cur.rooms = sorted(cur_rooms | new_rooms)
            cur.evidence = list(dict.fromkeys(cur.evidence + it.evidence))[:12]
            cur.confidence = round(max(cur.confidence, it.confidence), 2)
            if not cur.specification and it.specification:
                cur.specification = it.specification
            if not cur.size_label and it.size_label:
                cur.size_label = it.size_label
            if it.source_sheet and cur.source_sheet and it.source_sheet not in cur.source_sheet:
                cur.source_sheet = f"{cur.source_sheet}; {it.source_sheet}"
        for r in p.rooms:
            match = next((x for x in out.rooms if x.name == r.name), None)
            if match is None:
                out.rooms.append(r)
            else:
                for f in ("area_m2", "perimeter_m", "ceiling_height_m", "floor_finish", "ceiling_finish"):
                    if getattr(match, f) in (None, "") and getattr(r, f) not in (None, ""):
                        setattr(match, f, getattr(r, f))
                match.wall_finishes = sorted(set(match.wall_finishes) | set(r.wall_finishes))
                match.evidence = list(dict.fromkeys(match.evidence + r.evidence))[:8]
                match.confidence = max(match.confidence, r.confidence)
    # enrich descriptions from legend
    for it in out.items:
        if it.code and it.code.upper() in out.legend and not it.specification:
            it.specification = out.legend[it.code.upper()]
    return out
