"""Orchestrator: DXF file -> structural read result -> MeasurementExtraction.

read_structural_dxf() runs the whole chain: entities -> exclusions -> schedules ->
columns -> beams -> slabs. structural_to_measurement() maps the result onto the
app's element shapes so the existing measurement engine, review screen and Excel
export work unchanged.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.extract.structural.beams import BeamResult, find_beams
from app.extract.structural.columns import ColumnResult, match_columns
from app.extract.structural.config import DEFAULT_CONFIG, StructuralConfig
from app.extract.structural.entities import RawEntities, extract_entities
from app.extract.structural.exclusions import find_excluded, in_any_box
from app.extract.structural.schedule import BeamSchedule, parse_beam_schedule, parse_slab_schedule
from app.extract.structural.slabs import SlabResult, find_slabs
from app.models.schemas import MeasurementExtraction, MemberEl, SlabEl, WallEl

log = logging.getLogger(__name__)


@dataclass
class StructuralReadResult:
    columns: List[ColumnResult] = field(default_factory=list)
    beams: Dict[str, List[BeamResult]] = field(default_factory=dict)
    beam_fails: Dict[str, str] = field(default_factory=dict)
    slabs: List[SlabResult] = field(default_factory=list)
    schedule: Optional[BeamSchedule] = None
    slab_schedule: Dict[str, int] = field(default_factory=dict)
    region: Optional[List[float]] = None
    excluded_boxes: List[Tuple[float, float, float, float]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    # Kept in memory (never stored) so review questions can draw a crop of the real
    # linework around the part they ask about.
    plan_prims: list = field(default_factory=list, repr=False)
    plan_texts: list = field(default_factory=list, repr=False)
    hatches: list = field(default_factory=list, repr=False)
    # reader object -> element id, filled by structural_to_measurement
    # ("beam:B63#0", "col:3", "slab:7")
    element_ids: Dict[str, str] = field(default_factory=dict)

    def member_count(self) -> int:
        return len(self.columns) + len(self.beams)

    def summary(self) -> str:
        flagged = sum(1 for v in self.beams.values() for b in v if b.flags) \
            + sum(1 for c in self.columns if c.flags)
        slabs_found = sum(1 for s in self.slabs if s.found)
        return (f"{len(self.columns)} columns/walls, {len(self.beams)} beams "
                f"({len(self.beam_fails)} not traced), {slabs_found}/{len(self.slabs)} slab tags in a panel, "
                f"{flagged} flagged for review")


def read_structural_dxf(path, cfg: StructuralConfig = DEFAULT_CONFIG) -> StructuralReadResult:
    import ezdxf
    doc = ezdxf.readfile(str(path))
    res = StructuralReadResult()

    raw: RawEntities = extract_entities(doc, cfg)
    res.region = raw.region
    res.warnings += raw.notes

    words, boxes = find_excluded(doc)
    res.excluded_boxes = boxes
    if words:
        res.warnings.append("warning words found and those blocks skipped: "
                            + "; ".join(sorted({w[0][:60] for w in words})))
    if boxes:
        res.warnings.append(f"{len(boxes)} crossed-out block(s) skipped")

    # plan texts: inside the region and not crossed out
    def on_plan(t) -> bool:
        if in_any_box(t.cx, t.cy, boxes):
            return False
        r = raw.region
        return r is None or (r[0] <= t.cx <= r[2] and r[1] <= t.cy <= r[3])

    plan_texts = [t for t in raw.texts if on_plan(t)]
    plan_prims = [p for p in raw.prims
                  if not in_any_box(*(p.a if p.kind == "line" else p.c), boxes)]
    res.plan_texts, res.plan_prims, res.hatches = plan_texts, plan_prims, raw.columns

    res.schedule = parse_beam_schedule(raw.texts, raw.region, boxes)
    res.warnings += res.schedule.notes
    res.slab_schedule = parse_slab_schedule(raw.texts, raw.region, boxes)

    res.columns = match_columns(raw.columns, plan_texts, cfg)
    # A small hatch with no name and no size label is probably annotation (a legend
    # swatch, a detail): it may trim a beam end but must not cut a beam in two.
    beam_cols = []
    for hatch, matched in zip(raw.columns, res.columns):
        area = (hatch.bbox[2] - hatch.bbox[0]) * (hatch.bbox[3] - hatch.bbox[1])
        if hatch.kind != "hanging" and matched.name is None and matched.size is None and area < 350_000:
            hatch = type(hatch)(bbox=hatch.bbox, polys=hatch.polys, kind="hanging", aci=hatch.aci)
        beam_cols.append(hatch)
    res.beams, res.beam_fails = find_beams(plan_prims, beam_cols, plan_texts, res.schedule, cfg)
    res.slabs = find_slabs(plan_prims, raw.columns, plan_texts, res.slab_schedule, cfg, raw.region)

    found = set(res.beams)
    missing = [n for n in res.schedule.by_name if n not in found]
    if missing:
        res.warnings.append("in the beam schedule but not found on the plan: " + ", ".join(sorted(missing)[:20]))
    return res


# --------------------------------------------------------------------- mapping
def structural_to_measurement(res: StructuralReadResult, source_sheet: str, level: str = "",
                              floor_height_m: float = 3.0) -> MeasurementExtraction:
    """Map the geometric read onto the app's element shapes.

    Heights are NOT on a floor plan: columns and walls get the assumed floor height
    and a warning, until the section drawing is wired in.
    """
    ex = MeasurementExtraction()
    ex.assumptions.floor_height_m = floor_height_m
    ex.assumptions.notes.append("structural reader: exact sizes from the DXF; heights assumed")

    for ci, c in enumerate(res.columns):
        name = c.name or "?"
        w_mm, l_mm = (c.size if c.size else c.measured)
        conf = 0.95 if c.ok else 0.6
        ev = [f"hatch {c.measured[0]}x{c.measured[1]} mm"] + \
             ([f"label ({c.size[0]}X{c.size[1]})"] if c.size else []) + c.flags
        if c.kind != "column/wall":
            ev.append(c.kind)
        if name.startswith(("L", "W")) and not name.startswith("W?"):
            el = WallEl(tag=name, wall_type="rcc", length_m=l_mm / 1000, thickness_m=w_mm / 1000,
                                   height_m=floor_height_m, level=level, confidence=conf, evidence=ev,
                                   source_sheet=source_sheet,
                                   outline=[list(q) for pl in c.polys[:1] for q in pl],
                                   flags=list(c.flags))
            ex.walls.append(el)
        else:
            el = MemberEl(tag=name, kind="column", width_m=w_mm / 1000, depth_m=l_mm / 1000,
                          length_m=floor_height_m, level=level, confidence=conf, evidence=ev,
                          source_sheet=source_sheet,
                          outline=[list(q) for pl in c.polys[:1] for q in pl],
                          flags=list(c.flags))
            ex.members.append(el)
        res.element_ids[f"col:{ci}"] = el.id

    for name, pieces in res.beams.items():
        for b in pieces:
            length = max(b.length_mm, 100) / 1000
            ev = [f"size from {b.size_source}", f"traced length {b.length_mm} mm"
                  + (" (curved)" if b.curved else "")] + b.flags
            if b.kind:
                ev.append(b.kind)
            el = MemberEl(tag=name, kind="beam", width_m=b.width / 1000,
                          depth_m=(b.depth or 750) / 1000, length_m=length, level=level,
                          confidence=0.7 if b.flags else 0.95, evidence=ev,
                          source_sheet=source_sheet,
                          outline=[list(q) for q in b.geom], flags=list(b.flags))
            ex.members.append(el)
            res.element_ids[f"beam:{b.uid}"] = el.id

    for si, s in enumerate(res.slabs):
        if not s.found:
            ex.warnings.append(f"slab {s.tag}: no closed panel found around the tag")
            continue
        b_m = s.b_mm / 1000 or 1.0
        width_m = max(s.area_m2 / b_m, 0.05)   # keep the true area for L-shapes
        ev = [f"panel area {s.area_m2} m2, bounding {s.a_mm}x{s.b_mm} mm"]
        if s.rect_fill < 0.95:
            ev.append(f"not rectangular (fills {int(s.rect_fill * 100)}% of its rectangle); "
                      "length x width kept equal to the true area")
        # The panel is the area BETWEEN the beams, so there is no beam width left to take
        # off the soffit shuttering (beam_width_m=0).
        el = SlabEl(tag=s.tag, length_m=b_m, width_m=round(width_m, 3),
                    thickness_m=(s.thickness_mm or 150) / 1000, level=level, beam_width_m=0,
                    confidence=0.7 if s.flags else 0.9, evidence=ev + s.flags + ["panel between beams"],
                    source_sheet=source_sheet,
                    outline=[list(q) for q in s.poly], flags=list(s.flags))
        ex.slabs.append(el)
        res.element_ids[f"slab:{si}"] = el.id

    # The sheet merge dedupes elements by (tag, level): a second piece of the same
    # beam, or a second panel of the same slab mark, must keep its own row, so
    # repeated tags get a visible suffix.
    for lst in (ex.members, ex.walls, ex.slabs):
        seen: Dict[str, int] = {}
        for el in lst:
            n = seen.get(el.tag, 0) + 1
            seen[el.tag] = n
            if n > 1:
                el.tag = f"{el.tag} ({n})"

    ex.warnings += res.warnings
    for n, why in res.beam_fails.items():
        ex.warnings.append(f"beam {n}: {why}")
    if res.columns or res.beams:
        ex.warnings.append("column and wall heights are assumed "
                           f"({floor_height_m} m): confirm with the section drawing")
    return ex
