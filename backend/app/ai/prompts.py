"""Prompt text + flat response models for the Gemini calls.

The response models are deliberately simple (no unions, no dict fields) because the
Gemini structured-output schema translator does not support them. They are mapped to
the canonical models in app/models/schemas.py by app/ai/mappers.py.
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

SYSTEM = (
    "You are a senior quantity surveyor and structural detailer working for Avighna Group (Mumbai real-estate "
    "developer). You read construction drawings with extreme care. You never invent values: every number you "
    "output must be visible on the sheet, in the text listing, or in the measured facts you are given. "
    "When something is unreadable, leave it null and lower the confidence. Output strict JSON only."
)

# ----------------------------------------------------------------------------- classification
class AISheetClass(BaseModel):
    sheet_type: Literal[
        "beam_schedule", "beam_plan", "column_schedule", "column_plan", "slab_plan", "framing_plan",
        "wall_schedule", "staircase", "foundation", "section_detail", "general_notes", "title_or_index",
        "ga_plan", "setting_out_plan", "furniture_plan", "floor_finishes_plan", "wall_finishes_plan",
        "ceiling_plan", "power_plan", "sectional_elevation", "joinery_detail", "door_detail",
        "typical_detail", "finishes_legend", "lighting_schedule", "ffe_schedule", "perspective",
        "architectural", "interior", "mep", "other",
    ] = "other"
    discipline: Literal["structural", "architectural", "interior", "mep", "other"] = "other"
    drawing_number: Optional[str] = None
    title: Optional[str] = None
    level: Optional[str] = None
    scale: Optional[str] = None
    units: Literal["mm", "cm", "m", "unknown"] = "unknown"
    project: Optional[str] = None
    relevant_for_bbs: bool = False
    relevant_for_boq: bool = False
    confidence: float = 0.5
    summary: str = ""


def classify_prompt(file_name: str, page_no: int, title_hints: List[str], text_sample: str) -> str:
    return f"""Classify this construction drawing sheet.

File: {file_name}, page/layout: {page_no}
Title-block / corner texts: {' | '.join(title_hints[:80])}

First text items on the sheet (normalised coordinates 0-1000, y=0 at top):
{text_sample}

Rules:
- sheet_type: pick the single best type. Structural reinforcement sheets (beam/column/slab schedules, framing plans with bar callouts) set relevant_for_bbs=true.
- Interior fit-out sheets that carry measurable finishes, joinery, lighting, FF&E, doors or room areas (floor/wall/ceiling finish plans, enlarged plans, joinery details, elevations with finish tags, legends/schedules) set relevant_for_boq=true. Cover pages, drawing lists, perspectives and setting-out plans are not relevant.
- units: what the dimension strings are in (the general notes often say "ALL DIMENSIONS ARE IN MILLIMETERS/CENTIMETERS").
- drawing_number e.g. "KR-AGO-ID-GA-103" or "9680/P.P/13"; level e.g. "14th Floor"; scale e.g. "1:75".
- summary: one sentence on what can be measured from this sheet."""


# ----------------------------------------------------------------------------- structural
class AIBarGroup(BaseModel):
    count: int
    dia_mm: int


class AIStirrup(BaseModel):
    dia_mm: int
    spacing_mm: float
    zone: Literal["end", "mid", "full"] = "full"
    legs: int = 2


class AIBeam(BaseModel):
    tag: str
    nos: int = 1
    span_mm: float = Field(description="Clear span between supports in mm")
    width_mm: float
    depth_mm: float
    bottom_bars: List[AIBarGroup] = Field(default_factory=list)
    top_bars: List[AIBarGroup] = Field(default_factory=list)
    extra_top_left: List[AIBarGroup] = Field(default_factory=list)
    extra_top_right: List[AIBarGroup] = Field(default_factory=list)
    extra_bottom_mid: List[AIBarGroup] = Field(default_factory=list)
    bottom_curtail: List[AIBarGroup] = Field(default_factory=list)
    sfr_bars: List[AIBarGroup] = Field(default_factory=list, description="Side face bars per face")
    stirrups: List[AIStirrup] = Field(default_factory=list)
    left_support: Literal["end", "continuous"] = "end"
    right_support: Literal["end", "continuous"] = "end"
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)
    remarks: Optional[str] = None


class AISlabLayer(BaseModel):
    dia_mm: int
    spacing_mm: float
    bent_up: bool = False


class AISlab(BaseModel):
    tag: str
    nos: int = 1
    short_span_mm: float
    long_span_mm: float
    thickness_mm: float
    short_main: Optional[AISlabLayer] = None
    long_main: Optional[AISlabLayer] = None
    short_top_dist_end: Optional[AISlabLayer] = None
    long_top_dist_end: Optional[AISlabLayer] = None
    short_top_cont_edge: Optional[AISlabLayer] = None
    long_top_cont_edge: Optional[AISlabLayer] = None
    one_way: bool = False
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)
    remarks: Optional[str] = None


class AITie(BaseModel):
    dia_mm: int
    spacing_mm: float
    kind: Literal["main_ring", "inner_tie", "cross_tie"] = "main_ring"
    per_layer: int = 1
    leg_length_mm: Optional[float] = None


class AIColumn(BaseModel):
    tag: str
    nos: int = 1
    length_mm: float
    width_mm: float
    height_mm: float = Field(description="Floor-to-floor height; use the level height from notes if not on the sheet")
    vertical_bars: List[AIBarGroup] = Field(default_factory=list)
    ties: List[AITie] = Field(default_factory=list)
    shape: Literal["rectangular", "L", "T", "circular"] = "rectangular"
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)
    remarks: Optional[str] = None


class AIWall(BaseModel):
    tag: str
    nos: int = 1
    length_mm: float
    thickness_mm: float
    height_mm: float
    vertical: Optional[AISlabLayer] = None
    horizontal: Optional[AISlabLayer] = None
    faces: int = 2
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)
    remarks: Optional[str] = None


class AIFlight(BaseModel):
    name: str
    width_mm: float
    waist_mm: float
    going_mm: float
    rise_mm: float
    landing_a_mm: float = 0
    landing_b_mm: float = 0
    main: Optional[AISlabLayer] = None
    dist: Optional[AISlabLayer] = None


class AIStair(BaseModel):
    tag: str
    nos: int = 1
    flights: List[AIFlight] = Field(default_factory=list)
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)
    remarks: Optional[str] = None


class AIGeneralNotes(BaseModel):
    ld_factor: Optional[float] = None
    cover_beam_mm: Optional[float] = None
    cover_slab_mm: Optional[float] = None
    cover_column_mm: Optional[float] = None
    floor_height_mm: Optional[float] = None
    concrete_grade: Optional[str] = None
    steel_grade: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


class AIStructuralExtraction(BaseModel):
    beams: List[AIBeam] = Field(default_factory=list)
    slabs: List[AISlab] = Field(default_factory=list)
    columns: List[AIColumn] = Field(default_factory=list)
    walls: List[AIWall] = Field(default_factory=list)
    stairs: List[AIStair] = Field(default_factory=list)
    general_notes: AIGeneralNotes = Field(default_factory=AIGeneralNotes)
    warnings: List[str] = Field(default_factory=list)


def structural_prompt(sheet_label: str, units: str, tables_md: str, text_listing: str,
                      known_notes: str) -> str:
    return f"""Extract every reinforced-concrete member on this sheet so a Bar Bending Schedule can be computed.

Sheet: {sheet_label}. Drawing units for dimensions: {units}. Convert everything you output to MILLIMETRES.
Known general notes so far: {known_notes or 'none'}

The image is the plotted sheet. Below is the EXACT machine text from the drawing (so you do not need to guess digits), first any schedule tables rebuilt as markdown, then all text items with normalised coordinates (x,y in 0-1000, y=0 at top), bracketed text is the CAD layer.

{tables_md}

TEXT ITEMS:
{text_listing}

Indian detailing conventions: "2-T20" / "2Y20" / "2-#20" = 2 bars of 20 mm; "T8@100 c/c" = 8 mm stirrups at 100 mm centres; "2L" / "4L" = legs; "230x750" = width x depth in mm; "(2 nos)" after a tag = number of identical members; beam tags B1A, FB12, PB3; column tags C6, L1 (lift wall); slab panels S1, S3 "near C6"; NSW = non-structural wall / pardi / upstand; "Alt. Bent Up" = alternate bars cranked.
For beams: span = clear span between supports (use the dimension strings); supports are "end" when the beam ends at a column/wall edge and "continuous" when it continues into another beam/support. Put stirrup spacings that differ at ends vs middle as separate zones ("end" and "mid").
For slabs: short span and long span of the panel, thickness, main bars each way, top bars at discontinuous edges (dist. end) and continuous edges.
For columns: section size, floor height, vertical bars, main ring + inner ties with spacing (and per-layer counts).
Evidence: quote the exact text fragments you used (tag, size, bar callouts). Confidence 0-1 per member. If the sheet has no RC members, return empty lists with a warning."""


# ----------------------------------------------------------------------------- fit-out
class AILegendEntry(BaseModel):
    code: str
    description: str


class AIFitoutItem(BaseModel):
    division: Literal["preliminaries", "finishes", "joinery", "doors", "lighting", "ffe", "mep", "other"] = "finishes"
    section: str = Field(description="Floor Finishes | Wall Finishes | Ceilings | Skirting & Trims | Glazing & Partitions | Joinery | Doors | Lighting | Chairs | Tables | Loose Furniture | Accessories | Other")
    code: Optional[str] = None
    description: str
    unit: Literal["m2", "lm", "nos", "m3", "kg", "item", "ls"] = "nos"
    qty: float = 0
    qty_basis: Literal["measured", "counted", "estimated", "manual"] = "estimated"
    rooms: List[str] = Field(default_factory=list)
    size_label: Optional[str] = None
    specification: Optional[str] = None
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)
    remarks: Optional[str] = None


class AIRoom(BaseModel):
    name: str
    area_m2: Optional[float] = None
    perimeter_m: Optional[float] = None
    ceiling_height_m: Optional[float] = None
    floor_finish: Optional[str] = None
    wall_finishes: List[str] = Field(default_factory=list)
    ceiling_finish: Optional[str] = None
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)


class AIFitoutExtraction(BaseModel):
    items: List[AIFitoutItem] = Field(default_factory=list)
    rooms: List[AIRoom] = Field(default_factory=list)
    legend: List[AILegendEntry] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


def fitout_prompt(sheet_label: str, sheet_type: str, units: str, measured_facts: str,
                  text_listing: str, known_legend: str) -> str:
    return f"""Extract every measurable interior fit-out item on this sheet for a Bill of Quantities.

Sheet: {sheet_label} (type: {sheet_type}). Drawing units: {units}. Output lengths in metres, areas in m2.
Legend known so far (code -> description): {known_legend or 'none yet'}

MEASURED FACTS (computed deterministically from the CAD geometry; trust these numbers over anything you estimate):
{measured_facts}

EXACT machine text on the sheet (normalised coordinates 0-1000, y=0 at top; [layer] in brackets):
{text_listing}

What to produce
- items: one line per finish code / joinery item / fixture type visible on THIS sheet, with the quantity this sheet supports.
  * Floor finishes (FC-xxx): unit m2 per code; use measured hatch areas (qty_basis "measured") or room areas from the facts; name the rooms.
  * Wall finishes (WC-/WP-/GL-/MT-/VN- etc. on wall finish plans/elevations): unit m2 = wall length x height (height from FCL/FFL levels or notes); qty_basis "estimated" when you multiply.
  * Ceilings (CL-xxx) m2; bulkheads/pelmets lm; skirting (SK-xxx) lm = room perimeter minus openings; trims lm.
  * Joinery items J-001 ... with size_label "L x W x H" from the dimensions, unit nos, qty_basis "counted".
  * Lighting (LI-xxx) and FF&E (CH-/TB-/SF-/ACC- etc.) counted from symbols/tags: unit nos, qty_basis "counted".
  * Doors (D-xx) nos with size.
- rooms: every named room with area/perimeter from the facts and its finishes.
- legend: every code->description pair you can read (finish legends, lighting/FF&E schedules).
Never invent a quantity. If a quantity cannot be supported, set qty 0 and explain in remarks. Evidence must quote the sheet text. Confidence 0-1."""
