"""Deterministic fallbacks used when the AI is disabled (or as a sanity baseline).

- classify_sheet_heuristic: keyword classification from the sheet text.
- fitout_items_from_facts: BOQ items straight from measured CAD facts (areas / counts).
- structural_members_heuristic: beams/columns from schedule-like text via regex callouts.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple  # noqa: F401

from app.extract.callouts import parse_bar_groups, parse_member_tag, parse_size_mm, parse_all_spacings
from app.extract.fitout_geometry import MeasuredFacts
from app.extract.inventory import SheetInventory
from app.models.schemas import (
    BeamSpec, ColumnSpec, ColumnTie, FitoutExtraction, FitoutItem, RoomRecord, SheetClassification,
    StirrupZone, StructuralExtraction,
)

_TYPE_KEYWORDS: List[Tuple[str, str, str]] = [
    # (regex on text, sheet_type, discipline)
    (r"beam\s*schedule|beam\s*details?|beam\s*reinf", "beam_schedule", "structural"),
    (r"column\s*schedule|column\s*details?", "column_schedule", "structural"),
    (r"slab\s*reinf|slab\s*plan|slab\s*details?|bottom\s*reinf|top\s*reinf", "slab_plan", "structural"),
    (r"framing\s*plan|beam\s*layout|beam\s*plan", "framing_plan", "structural"),
    (r"stair", "staircase", "structural"),
    (r"footing|foundation|pile\s*cap|raft", "foundation", "structural"),
    (r"concrete\s*grade|grade\s*of\s*concrete|\bfe\s*500\b|\bm\s*[2-6]0\b", "general_notes", "structural"),
    (r"floor\s*finish", "floor_finishes_plan", "interior"),
    (r"wall\s*finish", "wall_finishes_plan", "interior"),
    (r"reflected\s*ceiling|ceiling\s*plan", "ceiling_plan", "interior"),
    (r"small\s*power|power\s*plan|lighting\s*plan", "power_plan", "interior"),
    (r"furniture\s*plan|furniture\s*layout", "furniture_plan", "interior"),
    (r"joinery\s*details?|joinery", "joinery_detail", "interior"),
    (r"door\s*details?|door\s*schedule", "door_detail", "interior"),
    (r"sectional\s*elevation|elevation", "sectional_elevation", "interior"),
    (r"typical\s*details?", "typical_detail", "interior"),
    (r"setting[\s-]*out", "setting_out_plan", "interior"),
    (r"general\s*arrangement|ga\s*plan", "ga_plan", "interior"),
    (r"drawing\s*list|cover\s*page|cover\s*sheet", "title_or_index", "other"),
    (r"perspective|3d\s*view|render", "perspective", "interior"),
]
_BBS_TYPES = {"beam_schedule", "beam_plan", "column_schedule", "column_plan", "slab_plan", "framing_plan",
              "wall_schedule", "staircase", "foundation", "section_detail"}
_BOQ_TYPES = {"ga_plan", "furniture_plan", "floor_finishes_plan", "wall_finishes_plan", "ceiling_plan", "power_plan",
              "sectional_elevation", "joinery_detail", "door_detail", "finishes_legend", "lighting_schedule",
              "ffe_schedule", "interior"}
_DWG_NO_RX = re.compile(r"\b([A-Z]{1,3}-[A-Z]{2,4}-[A-Z]{2}-[A-Z]{2}-\d{3}(?:-\d{3})?|\d{3,5}/[A-Z.]+/\d+[A-Z]?)\b")
_SCALE_RX = re.compile(r"\b1\s*:\s*(\d{1,4})\b")
_LEVEL_RX = re.compile(r"\b(\d{1,2}(?:st|nd|rd|th)\s*(?:floor|podium|basement|level)|ground\s*floor|terrace|basement\s*\d?)\b", re.I)


def classify_sheet_heuristic(inv: SheetInventory, title_hints: List[str]) -> SheetClassification:
    corpus = " ".join(title_hints + [t.text for t in inv.texts[:400]])
    low = corpus.lower()
    sheet_type, discipline, hits = "other", "other", 0
    # title-block text is more reliable than body text: weight hints x3
    fname = title_hints[0].lower() if title_hints else ""   # pipeline passes the file name first
    for rx, st, disc in _TYPE_KEYWORDS:
        n = (len(re.findall(rx, fname)) * 6 + len(re.findall(rx, " ".join(title_hints[1:]).lower())) * 3
             + len(re.findall(rx, low)))
        if n > hits:
            sheet_type, discipline, hits = st, disc, n
    bar_callouts = len(re.findall(r"\b\d{1,2}\s*-?\s*[TY#]\s*\d{1,2}\b|\b[TY]\s*\d{1,2}\s*@\s*\d{2,3}", corpus))
    if bar_callouts >= 6 and discipline != "structural":
        sheet_type, discipline = "framing_plan", "structural"
    # Units: an explicit "in mm" note wins; a "centimeters" note is overruled when the numbers
    # are clearly millimetres (title-block templates often carry stale boilerplate).
    mag = inv.units_hint if inv.units_hint in ("mm", "cm", "m") else "unknown"
    note = None
    if re.search(r"dimensions?\s+(?:are\s+)?in\s+(?:mm|millimet)", low):
        note = "mm"
    elif re.search(r"dimensions?\s+(?:are\s+)?in\s+(?:cm|centimet)", low):
        note = "cm"
    elif re.search(r"dimensions?\s+(?:are\s+)?in\s+met(?:er|re)s", low):
        note = "m"
    if note == "mm" or (note == "cm" and mag == "mm"):
        units = "mm"
    elif note:
        units = note
    else:
        units = mag if mag != "unknown" else "mm"
    dwg = _DWG_NO_RX.search(corpus)
    scale = _SCALE_RX.search(corpus)
    level = _LEVEL_RX.search(corpus)
    conf = min(0.4 + 0.1 * hits, 0.8) if hits else 0.3
    return SheetClassification(
        sheet_type=sheet_type, discipline=discipline, drawing_number=dwg.group(1) if dwg else None,
        title=None, level=level.group(1) if level else None, scale=f"1:{scale.group(1)}" if scale else None,
        units=units, project=None, relevant_for_bbs=sheet_type in _BBS_TYPES,
        relevant_for_boq=sheet_type in _BOQ_TYPES, confidence=conf,
        summary=f"Heuristic classification ({hits} keyword hits, {bar_callouts} bar callouts, {len(inv.texts)} texts)",
    )


_PREFIX_SECTION: Dict[str, Tuple[str, str, str]] = {
    # code prefix -> (division, section, unit)
    "FC": ("finishes", "Floor Finishes", "m2"), "FT": ("finishes", "Floor Finishes", "m2"),
    "WC": ("finishes", "Wall Finishes", "m2"), "WP": ("finishes", "Wall Finishes", "m2"), "WF": ("finishes", "Wall Finishes", "m2"),
    "CL": ("finishes", "Ceilings", "m2"), "CF": ("finishes", "Ceilings", "m2"),
    "SK": ("finishes", "Skirting & Trims", "lm"), "MT": ("finishes", "Skirting & Trims", "lm"),
    "GL": ("finishes", "Glazing & Partitions", "m2"), "ST": ("finishes", "Wall Finishes", "m2"),
    "J": ("joinery", "Joinery", "nos"), "JD": ("joinery", "Joinery", "nos"),
    "D": ("doors", "Doors", "nos"), "DR": ("doors", "Doors", "nos"),
    "LI": ("lighting", "Lighting", "nos"), "LT": ("lighting", "Lighting", "nos"), "L": ("lighting", "Lighting", "nos"),
    "CH": ("ffe", "Chairs", "nos"), "TB": ("ffe", "Tables", "nos"), "SF": ("ffe", "Loose Furniture", "nos"),
    "ACC": ("ffe", "Accessories", "nos"), "AC": ("ffe", "Accessories", "nos"), "FA": ("ffe", "Accessories", "nos"),
    "PL": ("ffe", "Accessories", "nos"), "AW": ("ffe", "Accessories", "nos"),
}


def fitout_items_from_facts(facts: MeasuredFacts, sheet_label: str, sheet_type: str) -> FitoutExtraction:
    out = FitoutExtraction()
    seen_codes = set()
    # measured finish areas
    for code, area in facts.area_by_code().items():
        prefix = code.split("-")[0]
        div, section, unit = _PREFIX_SECTION.get(prefix, ("finishes", "Other", "m2"))
        if unit == "nos":
            continue
        rooms = facts.rooms_by_code().get(code, [])
        kind = {"Floor Finishes": "Floor finish", "Wall Finishes": "Wall finish", "Ceilings": "Ceiling finish"}.get(section, "Finish")
        out.items.append(FitoutItem(division=div, section=section, code=code, description=f"{kind} {code} as per finishes schedule (area measured from CAD hatch)",
                                    unit="m2" if unit != "lm" else "lm", qty=round(area, 2), qty_basis="measured", rooms=rooms,
                                    confidence=0.75, evidence=[f"hatch area {area} m2 tagged {code}"], source_sheet=sheet_label))
        seen_codes.add(code)
    # counted tags / codes (fixtures, furniture, joinery)
    counts: Dict[str, int] = {}
    for src in (facts.attrib_counts, facts.code_counts):
        for txt, n in src.items():
            m = re.match(r"^([A-Z]{1,3})-(\d{2,3}[A-Z]?)$", txt.strip().upper())
            if m and txt.upper() not in counts:
                counts[txt.upper()] = n
    for code, n in sorted(counts.items()):
        if code in seen_codes:
            continue
        prefix = code.split("-")[0]
        if prefix not in _PREFIX_SECTION:
            continue
        div, section, unit = _PREFIX_SECTION[prefix]
        if unit != "nos":
            continue  # areas without hatches cannot be measured deterministically
        if sheet_type in ("joinery_detail", "door_detail") and div in ("joinery", "doors"):
            n = 1  # a detail sheet documents one item; the plan sheets count instances
        noun = {"joinery": "Joinery item", "doors": "Door", "lighting": "Light fitting", "ffe": section.rstrip("s") + " item"}.get(div, "Item")
        ref = {"joinery": "as per joinery details", "doors": "as per door schedule", "lighting": "as per lighting schedule",
               "ffe": "as per FF&E schedule"}.get(div, "as per drawings")
        out.items.append(FitoutItem(division=div, section=section, code=code, description=f"{noun} {code} {ref}",
                                    unit="nos", qty=n, qty_basis="counted", confidence=0.55,
                                    evidence=[f"{n} x '{code}' tag(s) on sheet"], source_sheet=sheet_label))
    # measured polyline lengths on skirting / trim / bulkhead layers -> lm items
    for layer, length in facts.length_by_layer_m.items():
        if length <= 0:
            continue
        low = layer.lower()
        if re.search(r"skirt", low):
            section, div, unit = "Skirting & Trims", "finishes", "lm"
        elif re.search(r"bulkhead|pelmet|cove|trim", low):
            section, div, unit = "Skirting & Trims", "finishes", "lm"
        elif re.search(r"paper|clad|panel|finish|veneer|fabric|\bwc-|\bwp-|\bwf-", low) and not re.search(r"hatch|pdf_|arch|con-", low):
            section, div, unit = "Wall Finishes", "finishes", "lm"
        elif re.search(r"ceil|clg", low):
            section, div, unit = "Ceilings", "finishes", "lm"
        else:
            continue
        label = re.sub(r"^(sq|kr|id|ar|a)[-_ ]*", "", layer, flags=re.I).replace("_", " ").strip(" -") or layer
        out.items.append(FitoutItem(division=div, section=section, code=None, description=f"{label.title()} (length from CAD layer {layer})",
                                    unit=unit, qty=round(length, 2), qty_basis="measured", confidence=0.5,
                                    evidence=[f"polyline length {length:.2f} m on layer {layer}"], source_sheet=sheet_label,
                                    remarks="length only; apply wall height / deduct openings when pricing in m2" if unit == "lm" and section == "Wall Finishes" else None))
    for r in facts.rooms:
        if not r.name.startswith("("):
            out.rooms.append(RoomRecord(name=r.name, area_m2=r.area_m2, perimeter_m=r.perimeter_m, source_sheet=sheet_label,
                                        confidence=0.7, evidence=[f"closed polyline on layer {r.layer}"]))
    if not out.items:
        out.warnings.append(f"{sheet_label}: no measurable facts without AI reading")
    return out


def structural_members_heuristic(inv: SheetInventory, sheet_label: str, floor_height_m: float = 3.0) -> StructuralExtraction:
    """Very conservative: only members whose tag, size and bars sit on the same text row."""
    out = StructuralExtraction()
    mh = re.search(r"(?:floor|storey|story)\s*(?:to\s*floor\s*)?height\s*:?\s*(\d{3,5})", inv.all_text(), re.I)
    if mh:
        v = float(mh.group(1))
        floor_height_m = v / 1000 if v > 100 else v
        out.general_notes.notes.append(f"floor height {floor_height_m} m read from sheet")
    rows: Dict[int, List] = {}
    tol = inv.row_tolerance()
    for t in inv.texts:
        rows.setdefault(int(round(t.cy / max(tol * 2, 1e-6))), []).append(t)
    for _k, items in rows.items():
        items.sort(key=lambda t: t.x)
        line = " ".join(t.text for t in items)
        tag = None
        first = re.split(r"\s{2,}|\t", line.strip())[0]
        for cand in (first, line.strip().split(" ")[0] if line.strip() else ""):
            m_nos = re.search(r"\((\d+)\s*nos?\.?\)", line, re.I)
            mt = parse_member_tag(cand + (f" ({m_nos.group(1)} nos)" if m_nos and "(" not in cand else ""))
            if mt and mt.kind in ("beam", "column"):
                tag = mt
                break
        if not tag:
            for t in items:
                mt = parse_member_tag(t.text)
                if mt and mt.kind in ("beam", "column"):
                    tag = mt
                    break
        if not tag:
            continue
        # strip member tags (B1, C12A, FB-3) and the "(n nos)" suffix so they cannot be read as bar counts
        body = re.sub(r"\((\d+)\s*nos?\.?\)", " ", line, flags=re.I)
        body = re.sub(r"\b(?:FB|PB|LB|SB|CB|TB|GB|B|FC|HC|PC|C|SW|S|L|W|ST|RW|CW)\s?-?\s?\d{1,3}[A-Z]?\b(?!\s*[xX×@])", " ", body)
        size = parse_size_mm(body)
        groups = parse_bar_groups(body)
        spacings = parse_all_spacings(body)
        if not size or not groups:
            continue
        # a lone 4-5 digit number (not part of a size / callout) is the span in mm
        rest = re.sub(r"\d{2,4}\s*[xX×]\s*\d{2,4}", " ", body)
        rest = re.sub(r"[TY#Øø]\s*\d{1,2}\s*@\s*\d{2,3}|\d{1,2}\s*[-–]\s*[TY#]?\s*\d{1,2}", " ", rest)
        spans = [float(x) for x in re.findall(r"(?<![\d.])(\d{4,5})(?![\d.])", rest) if 900 <= float(x) <= 20000]
        if tag.kind == "beam":
            zones: List[StirrupZone] = []
            if len(spacings) >= 2 and spacings[0].spacing_mm != spacings[1].spacing_mm:
                zones = [StirrupZone(dia_mm=spacings[0].dia_mm, spacing_mm=spacings[0].spacing_mm, legs=spacings[0].legs, zone="end"),
                         StirrupZone(dia_mm=spacings[1].dia_mm, spacing_mm=spacings[1].spacing_mm, legs=spacings[1].legs, zone="mid")]
            elif spacings:
                zones = [StirrupZone(dia_mm=spacings[0].dia_mm, spacing_mm=spacings[0].spacing_mm, legs=spacings[0].legs, zone="full")]
            span_m = spans[0] / 1000 if spans else 1.0
            out.beams.append(BeamSpec(tag=tag.tag, nos=tag.nos or 1, span_m=span_m, width_m=size[0] / 1000, depth_m=size[1] / 1000,
                                      bottom_bars=groups[:1], top_bars=groups[1:2], extra_top_left=groups[2:3], extra_top_right=groups[3:4],
                                      stirrups=zones, confidence=0.45 if spans else 0.3, evidence=[line[:160]], source_sheet=sheet_label,
                                      remarks=None if spans else "span not found on this row (set 1.0 m) - edit before use"))
        else:
            ties = []
            if spacings:
                ties.append(ColumnTie(dia_mm=spacings[0].dia_mm, spacing_mm=spacings[0].spacing_mm, kind="main_ring"))
            for s in spacings[1:3]:
                ties.append(ColumnTie(dia_mm=s.dia_mm, spacing_mm=s.spacing_mm, kind="inner_tie", per_layer=1))
            out.columns.append(ColumnSpec(tag=tag.tag, nos=tag.nos or 1, length_m=size[0] / 1000, width_m=size[1] / 1000,
                                          height_m=floor_height_m, vertical_bars=groups[:1] or groups,
                                          ties=ties, confidence=0.4, evidence=[line[:160]], source_sheet=sheet_label,
                                          remarks="floor height assumed - verify height and tie layout"))
    if not out.beams and not out.columns:
        out.warnings.append(f"{sheet_label}: no members recognised without AI reading")
    return out


def measurement_from_facts(facts: MeasuredFacts, sheet_label: str) -> "MeasurementExtraction":
    """No-AI fallback for the measurement module: rooms from CAD room polygons (area + perimeter),
    doors/windows from tag counts. Dimensions default to a square of the same area."""
    import math
    from app.models.schemas import MeasurementExtraction, OpeningEl, RoomEl
    out = MeasurementExtraction()
    for r in facts.rooms:
        if r.name.startswith("(") or r.area_m2 <= 0:
            continue
        side = math.sqrt(r.area_m2)
        name = r.name.title()
        wet = bool(re.search(r"toilet|bath|wc|kitchen|utility|pantry|wash|balcony", name, re.I))
        out.rooms.append(RoomEl(name=name, length_m=round(side, 3), width_m=round(side, 3), area_m2=r.area_m2, perimeter_m=r.perimeter_m,
                                wet_area=wet, dado_height_m=2.1 if wet and "balcony" not in name.lower() else 0,
                                confidence=0.5, evidence=[f"closed outline on layer {r.layer}: {r.area_m2} m2, perimeter {r.perimeter_m} m"],
                                source_sheet=sheet_label, remarks="size from CAD outline; L x B shown as equivalent square"))
    for txt, n in list(facts.attrib_counts.items()) + list(facts.code_counts.items()):
        m = re.match(r"^(D|DR|W|WN|V)[- ]?(\d{1,2}[A-Z]?)$", txt.strip().upper())
        if not m:
            continue
        kind = "door" if m.group(1) in ("D", "DR") else ("ventilator" if m.group(1) == "V" else "window")
        if any(o.tag == txt.upper() for o in out.openings):
            continue
        w, h = (1.0, 2.1) if kind == "door" else ((0.6, 0.45) if kind == "ventilator" else (1.5, 1.2))
        out.openings.append(OpeningEl(tag=txt.upper(), kind=kind, width_m=w, height_m=h, count=n, confidence=0.3,
                                      evidence=[f"{n} x '{txt}' tag(s) on sheet; size assumed, check schedule"], source_sheet=sheet_label))
    if not out.rooms and not out.openings:
        out.warnings.append(f"{sheet_label}: nothing measurable without AI reading")
    return out
