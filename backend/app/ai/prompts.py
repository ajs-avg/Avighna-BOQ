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


# ----------------------------------------------------------------------------- measurement (the product)
class AIMRoom(BaseModel):
    name: str
    level: str = ""
    length_mm: float = Field(description="Internal clear length")
    width_mm: float = Field(description="Internal clear width")
    height_mm: Optional[float] = Field(None, description="Floor to ceiling; null if not on sheet")
    area_m2: Optional[float] = Field(None, description="Only for non-rectangular rooms, from measured facts or dimensions")
    perimeter_m: Optional[float] = None
    floor_finish: str = Field("", description="e.g. 'vitrified tile flooring 600x600 mm' or code + description from legend")
    wall_finish: str = Field("", description="paint / wallpaper / tiles ...")
    ceiling_finish: str = ""
    skirting_mm: float = 100
    dado_height_m: float = Field(0, description="Wall tiles height for bathrooms/kitchens, else 0")
    wet_area: bool = False
    plastered: bool = Field(True, description="False when walls are RCC/Mivan (putty only)")
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)


class AIMOpening(BaseModel):
    tag: str
    kind: Literal["door", "window", "opening", "ventilator"] = "door"
    width_mm: float
    height_mm: float
    count: int = 1
    room: str = ""
    wall_tag: str = ""
    description: str = ""
    level: str = ""
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)


class AIMWall(BaseModel):
    tag: str
    wall_type: Literal["rcc", "block", "partition", "glass", "other"] = "block"
    length_mm: float
    thickness_mm: float
    height_mm: float
    count: int = 1
    room: str = ""
    level: str = ""
    both_faces: bool = True
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)


class AIMSlab(BaseModel):
    tag: str = "S1"
    length_mm: float
    width_mm: float
    thickness_mm: float = 150
    count: int = 1
    level: str = ""
    beam_width_mm: float = 230
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)


class AIMMember(BaseModel):
    tag: str
    kind: Literal["column", "beam"] = "column"
    width_mm: float
    depth_mm: float
    length_mm: float = Field(description="Height for columns, clear span for beams")
    count: int = 1
    level: str = ""
    slab_thickness_mm: float = 0
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)


class AIMMisc(BaseModel):
    tag: Optional[str] = None
    description: str
    unit: Literal["nos", "sqm", "rmt", "cum", "kg", "LS"] = "nos"
    qty: float
    trade: str = "Miscellaneous"
    room: str = ""
    level: str = ""
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)


class AIMAssumptions(BaseModel):
    floor_height_mm: Optional[float] = None
    wall_thickness_mm: Optional[float] = None
    slab_thickness_mm: Optional[float] = None
    construction: Literal["mivan", "conventional"] = "conventional"
    concrete_grade: str = "M40"
    notes: List[str] = Field(default_factory=list)


class AIMeasurementExtraction(BaseModel):
    rooms: List[AIMRoom] = Field(default_factory=list)
    openings: List[AIMOpening] = Field(default_factory=list)
    walls: List[AIMWall] = Field(default_factory=list)
    slabs: List[AIMSlab] = Field(default_factory=list)
    members: List[AIMMember] = Field(default_factory=list)
    misc: List[AIMMisc] = Field(default_factory=list)
    assumptions: AIMAssumptions = Field(default_factory=AIMAssumptions)
    warnings: List[str] = Field(default_factory=list)


def measurement_prompt(sheet_label: str, sheet_type: str, units: str, measured_facts: str,
                       text_listing: str, known_assumptions: str) -> str:
    return f"""You are taking off quantities from this construction drawing for an Indian measurement sheet
(IS 1200 style: every room, wall, opening and member becomes a row Nos x L x B x H).

Sheet: {sheet_label} (type: {sheet_type}). Drawing units: {units}. Output ALL dimensions in MILLIMETRES.
Project assumptions known so far: {known_assumptions or 'none'}

MEASURED FACTS from the CAD geometry (trust these numbers over estimates; rooms here come with area and perimeter):
{measured_facts}

EXACT machine text on the sheet (normalised coordinates 0-1000, y=0 at top; [layer] in brackets):
{text_listing}

Extract, as completely as you can:
- rooms: every named space (bedroom, living, kitchen, toilet, balcony, passage, lobby...) with internal clear length x width
  (from dimension strings; if the room is irregular give area_m2/perimeter_m from the measured facts), floor-to-ceiling height
  if shown (else null), finishes from the finish schedule/legend or notes (floor, wall, ceiling), skirting, dado height for wet
  areas, wet_area true for toilets/bathrooms/kitchen/utility/balcony, plastered=false when walls are RCC (Mivan).
- openings: every door/window/ventilator with tag, size, count, the room it serves and the wall tag if walls are tagged;
  description from the door/window schedule (type, material).
- walls: when the drawing shows walls with tags or clear lengths (structural/Mivan plans, wall layouts): tag, type
  (rcc / block / partition / glass), length, thickness, height, count, room, level.
- slabs / members (columns, beams): when a structural plan or schedule is on the sheet, with sizes and counts.
- misc: every other countable item a quantity surveyor would bill from THIS sheet - sanitary fixtures, kitchen platform,
  railings (rmt), lofts, electrical points (nos), AC points, lights, joinery, wardrobes, lintels, chajjas, parapets etc.
  Use your own judgement for the right unit (nos / sqm / rmt / cum / kg / LS) and a clear CPWD-style description.
- assumptions: floor height, wall/slab thickness, construction type and concrete grade from the notes.
Rules: never invent dimensions; copy them from the text. Give evidence (quoted text) and confidence per element. If the
sheet has nothing measurable (cover, index, perspective), return empty lists with a warning."""
