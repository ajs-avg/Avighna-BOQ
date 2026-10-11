"""
Shared data contract for the Avighna BOQ platform.

Everything that crosses a boundary (API <-> frontend, extractor <-> engine,
engine <-> Excel export, repository <-> database) is defined here so that
the whole system speaks one language.

Units: lengths in metres, bar diameters in millimetres, spacing in millimetres,
weights in kilograms unless a field name says otherwise.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field
from typing_extensions import Annotated


def new_id() -> str:
    return uuid4().hex[:12]


# --------------------------------------------------------------------------- #
# Company standards (the constants that drive every BBS formula)
# --------------------------------------------------------------------------- #
class Standards(BaseModel):
    """Avighna / IS-456 style BBS constants. Defaults reproduce the
    'Measurement Sheet_14th Floor Reinforcement.xlsx' logic exactly."""

    ld_factor: float = Field(39, description="Development length as a multiple of bar dia (Ld = 39d)")
    anchorage_extra_d: float = Field(10, description="Extra dia multiples added to Ld for an L-bend anchorage ((Ld+10)d)")
    cover_beam_mm: float = 30
    cover_slab_mm: float = 20
    cover_column_mm: float = 40
    cover_wall_mm: float = 20
    cover_stair_mm: float = 20
    hook_length_d: float = Field(10, description="Hook length per stirrup end as multiple of dia")
    stirrup_corners: int = Field(5, description="Bend corners counted for a closed rectangular stirrup incl. hooks")
    bend_deduction_d: float = Field(0.6, description="Length deducted per bend corner as multiple of dia")
    min_straight_anchorage_m: float = Field(0.3, description="MAX(10d, 0.3m) straight extension at continuous ends")
    extra_bar_span_fraction: float = Field(1 / 3, description="Extra top bar length as a fraction of span")
    curtail_fraction: float = Field(0.1, description="Bottom curtail bar stops 0.1L from each support")
    end_zone_span_fraction: float = Field(1 / 3, description="Close-spacing stirrup zone at each beam end")
    stirrup_end_offset_m: float = Field(0.05, description="First stirrup offset from support face")
    slab_min_anchorage_m: float = Field(0.2, description="Slab bar anchorage MAX(10d, 0.2)")
    slab_bentup_factor: float = Field(0.42, description="Extra length of an alternate bent-up bar = 0.42 x (D - 2c)")
    slab_dist_end_fraction: float = Field(1 / 7, description="Top bar zone at discontinuous slab edge = L/7")
    slab_cont_edge_fraction: float = Field(0.3, description="Top bar zone at continuous slab edge = 0.3L")
    sfr_min_depth_m: float = Field(0.75, description="Side-face reinforcement provided when beam depth >= this")
    unit_weight_kg_per_m: Dict[int, float] = Field(
        default_factory=lambda: {
            6: 0.222, 8: 0.395, 10: 0.617, 12: 0.888, 16: 1.58,
            20: 2.47, 25: 3.85, 32: 6.31, 40: 9.86,
        }
    )
    diameters_in_summary: List[int] = Field(default_factory=lambda: [8, 10, 12, 16, 20, 25, 32])

    def unit_weight(self, dia_mm: int) -> float:
        if dia_mm in self.unit_weight_kg_per_m:
            return self.unit_weight_kg_per_m[dia_mm]
        # IS 1786 formula d^2/162
        return round(dia_mm * dia_mm / 162.0, 3)


# --------------------------------------------------------------------------- #
# Extraction results (what the drawing intelligence layer produces)
# --------------------------------------------------------------------------- #
class BarGroup(BaseModel):
    """n bars of one diameter, e.g. '2-T20'."""
    count: int = Field(ge=0)
    dia_mm: int = Field(ge=6, le=50)
    note: Optional[str] = None


class StirrupZone(BaseModel):
    dia_mm: int
    spacing_mm: float
    zone: Literal["end", "mid", "full"] = "full"
    legs: int = 2


SupportType = Literal["end", "continuous"]


class BBox(BaseModel):
    """Location on the source sheet in page/model units so the UI can highlight it."""
    x0: float
    y0: float
    x1: float
    y1: float
    space: Literal["page", "model"] = "page"


class MemberBase(BaseModel):
    id: str = Field(default_factory=new_id)
    tag: str = Field(description="Member label on the drawing e.g. B1A, C6, S3, L1")
    nos: int = Field(1, ge=1, description="Number of identical members")
    confidence: float = Field(0.5, ge=0, le=1)
    evidence: List[str] = Field(default_factory=list, description="Verbatim text fragments that support this member")
    source_sheet: Optional[str] = None
    source_bbox: Optional[BBox] = None
    remarks: Optional[str] = None


class BeamSpec(MemberBase):
    kind: Literal["beam"] = "beam"
    span_m: float = Field(gt=0, description="Clear span between supports (L)")
    width_m: float = Field(gt=0, description="B")
    depth_m: float = Field(gt=0, description="D")
    bottom_bars: List[BarGroup] = Field(default_factory=list)
    top_bars: List[BarGroup] = Field(default_factory=list)
    extra_top_left: List[BarGroup] = Field(default_factory=list)
    extra_top_right: List[BarGroup] = Field(default_factory=list)
    extra_bottom_mid: List[BarGroup] = Field(default_factory=list)
    bottom_curtail: List[BarGroup] = Field(default_factory=list, description="Bottom bars curtailed at 0.1L")
    sfr_bars: List[BarGroup] = Field(default_factory=list, description="Side face reinforcement per face")
    stirrups: List[StirrupZone] = Field(default_factory=list)
    left_support: SupportType = "end"
    right_support: SupportType = "end"


class SlabLayer(BaseModel):
    dia_mm: int
    spacing_mm: float
    bent_up: bool = False
    note: Optional[str] = None


class SlabSpec(MemberBase):
    kind: Literal["slab"] = "slab"
    length_m: float = Field(gt=0, description="Short span Lx")
    width_m: float = Field(gt=0, description="Long span Ly")
    thickness_m: float = Field(gt=0)
    short_main: Optional[SlabLayer] = None
    long_main: Optional[SlabLayer] = None
    short_top_dist_end: Optional[SlabLayer] = Field(None, description="Top bars at discontinuous short edges")
    long_top_dist_end: Optional[SlabLayer] = None
    short_top_cont_edge: Optional[SlabLayer] = Field(None, description="Top bars at continuous edges (0.3L zone)")
    long_top_cont_edge: Optional[SlabLayer] = None
    extra_top: List[SlabLayer] = Field(default_factory=list)
    one_way: bool = False


class ColumnTie(BaseModel):
    dia_mm: int
    spacing_mm: float
    kind: Literal["main_ring", "inner_tie", "cross_tie"] = "main_ring"
    per_layer: int = 1
    leg_length_m: Optional[float] = Field(None, description="For inner/cross ties: straight length between hooks")


class ColumnSpec(MemberBase):
    kind: Literal["column"] = "column"
    length_m: float = Field(gt=0, description="Section dimension a")
    width_m: float = Field(gt=0, description="Section dimension b")
    height_m: float = Field(gt=0, description="Floor-to-floor height")
    vertical_bars: List[BarGroup] = Field(default_factory=list)
    ties: List[ColumnTie] = Field(default_factory=list)
    lap_at_floor: bool = True
    shape: Literal["rectangular", "L", "T", "circular"] = "rectangular"


class WallSpec(MemberBase):
    kind: Literal["wall"] = "wall"
    length_m: float = Field(gt=0)
    thickness_m: float = Field(gt=0)
    height_m: float = Field(gt=0)
    vertical: Optional[SlabLayer] = None
    horizontal: Optional[SlabLayer] = None
    faces: int = Field(2, ge=1, le=2, description="1 = single mesh, 2 = double mesh")
    starter_lap: bool = True


class StairFlight(BaseModel):
    name: str
    width_m: float
    waist_m: float
    going_m: float = Field(description="Horizontal length of the flight")
    rise_m: float = Field(description="Vertical rise of the flight")
    landing_a_m: float = 0.0
    landing_b_m: float = 0.0
    main: Optional[SlabLayer] = None
    dist: Optional[SlabLayer] = None


class StairSpec(MemberBase):
    kind: Literal["stair"] = "stair"
    flights: List[StairFlight] = Field(default_factory=list)


MemberSpec = Annotated[
    Union[BeamSpec, SlabSpec, ColumnSpec, WallSpec, StairSpec],
    Field(discriminator="kind"),
]


class GeneralNotes(BaseModel):
    ld_factor: Optional[float] = None
    cover_beam_mm: Optional[float] = None
    cover_slab_mm: Optional[float] = None
    cover_column_mm: Optional[float] = None
    concrete_grade: Optional[str] = None
    steel_grade: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


class SheetClassification(BaseModel):
    sheet_type: Literal[
        "beam_schedule", "beam_plan", "column_schedule", "column_plan",
        "slab_plan", "framing_plan", "wall_schedule", "staircase",
        "foundation", "section_detail", "general_notes", "title_or_index",
        "architectural", "interior", "mep", "other",
        "ga_plan", "setting_out_plan", "furniture_plan", "floor_finishes_plan", "wall_finishes_plan",
        "ceiling_plan", "power_plan", "sectional_elevation", "joinery_detail", "door_detail",
        "typical_detail", "finishes_legend", "lighting_schedule", "ffe_schedule", "perspective",
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


class StructuralExtraction(BaseModel):
    beams: List[BeamSpec] = Field(default_factory=list)
    slabs: List[SlabSpec] = Field(default_factory=list)
    columns: List[ColumnSpec] = Field(default_factory=list)
    walls: List[WallSpec] = Field(default_factory=list)
    stairs: List[StairSpec] = Field(default_factory=list)
    general_notes: GeneralNotes = Field(default_factory=GeneralNotes)
    warnings: List[str] = Field(default_factory=list)

    def member_count(self) -> int:
        return len(self.beams) + len(self.slabs) + len(self.columns) + len(self.walls) + len(self.stairs)



# --------------------------------------------------------------------------- #
# Product modules
# --------------------------------------------------------------------------- #
class Module(str, Enum):
    measurement = "measurement" # THE product: drawing -> measurement sheet -> BOQ -> materials
    structural = "structural"   # (legacy) RCC reinforcement -> Bar Bending Schedule (tons)
    fitout = "fitout"           # (legacy) Interior fit-out -> KR-style Bill of Quantities


# --------------------------------------------------------------------------- #
# Fit-out extraction (interior design drawings -> measurable items)
# --------------------------------------------------------------------------- #
Division = Literal["preliminaries", "finishes", "joinery", "doors", "lighting", "ffe", "mep", "other"]
Unit = Literal["m2", "lm", "nos", "m3", "kg", "item", "ls"]
QtyBasis = Literal["measured", "counted", "estimated", "manual"]

DIVISION_LABELS: Dict[str, str] = {
    "preliminaries": "DIV-01 - PRELIMINARIES",
    "finishes": "DIV-09 - FINISHES",
    "joinery": "DIV-09 - JOINERY",
    "doors": "DIV-08 - DOORS",
    "lighting": "DIV-13 - LIGHTING",
    "ffe": "FF&E",
    "mep": "DIV-15 - MEP",
    "other": "OTHER",
}


class FitoutItem(BaseModel):
    """One measurable line: 'FC-201 Cream Cremo Delicato stone flooring, 270 m2'."""
    id: str = Field(default_factory=new_id)
    division: Division = "finishes"
    section: str = Field("", description="Group inside the division e.g. Floor Finishes, Wall Finishes, Ceilings, Skirting & Trims, Joinery, Chairs, Tables")
    code: Optional[str] = Field(None, description="Finish / item code from the legend e.g. FC-201, WC-103, J-013, LI-501, CH-101")
    description: str
    unit: Unit = "nos"
    qty: float = Field(0, ge=0)
    qty_basis: QtyBasis = "estimated"
    rooms: List[str] = Field(default_factory=list, description="Rooms / spaces where this item occurs")
    size_label: Optional[str] = Field(None, description="e.g. 3375mm L x 700mm W x 1100mm H")
    specification: Optional[str] = Field(None, description="Brand / model / finish references from the spec legend")
    confidence: float = Field(0.5, ge=0, le=1)
    evidence: List[str] = Field(default_factory=list)
    source_sheet: Optional[str] = None
    source_bbox: Optional[BBox] = None
    rate: Optional[float] = Field(None, description="Optional unit rate entered by the reviewer")
    remarks: Optional[str] = None


class RoomRecord(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    area_m2: Optional[float] = None
    perimeter_m: Optional[float] = None
    ceiling_height_m: Optional[float] = None
    floor_finish: Optional[str] = None
    wall_finishes: List[str] = Field(default_factory=list)
    ceiling_finish: Optional[str] = None
    source_sheet: Optional[str] = None
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)


class FitoutExtraction(BaseModel):
    items: List[FitoutItem] = Field(default_factory=list)
    rooms: List[RoomRecord] = Field(default_factory=list)
    legend: Dict[str, str] = Field(default_factory=dict, description="code -> description from finish / lighting / FF&E legends")
    warnings: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# BOQ engine output (fit-out)
# --------------------------------------------------------------------------- #
class BOQLine(BaseModel):
    seq: int
    item_ref: str = Field(description="A, B, C ... within the section page, like the KR BOQ")
    item_id: str
    division: Division
    section: str
    code: Optional[str] = None
    description: str
    unit: Unit
    qty: float
    rate: Optional[float] = None
    amount: Optional[float] = None
    qty_basis: QtyBasis = "estimated"
    rooms: List[str] = Field(default_factory=list)
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)
    source_sheet: Optional[str] = None
    formula: str = ""


class BOQSection(BaseModel):
    division: Division
    division_label: str
    section: str
    lines: List[BOQLine]
    qty_by_unit: Dict[str, float] = Field(default_factory=dict)
    amount: float = 0.0


class BOQSummary(BaseModel):
    currency: str = "AED"
    vat_pct: float = 5.0
    divisions: List[Dict[str, Any]] = Field(default_factory=list, description="[{division, label, line_count, amount}]")
    line_count: int = 0
    qty_by_unit: Dict[str, float] = Field(default_factory=dict)
    priced_lines: int = 0
    subtotal: float = 0.0
    vat: float = 0.0
    grand_total: float = 0.0


class BOQResult(BaseModel):
    sections: List[BOQSection]
    rooms: List[RoomRecord] = Field(default_factory=list)
    summary: BOQSummary
    warnings: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Engine output (one bar row == one line in the Excel BBS)
# --------------------------------------------------------------------------- #
class BarRow(BaseModel):
    seq: int
    description: str
    dia_mm: int
    members: int = Field(description="No. of identical members (C column)")
    bars_per_member: float = Field(description="No. of bars per member (L column / 'Bars per Member')")
    total_bars: float
    spacing_mm: Optional[float] = None
    span_m: Optional[float] = Field(None, description="Length over which bars are distributed")
    a: float = 0.0
    b: float = 0.0
    c: float = 0.0
    d: float = 0.0
    e: float = 0.0
    f: float = 0.0
    g: float = 0.0
    bend_corners: int = 0
    cut_length_m: float
    weight_kg: float
    formula: str = Field("", description="Human readable trace of the calculation")
    shape: str = Field("straight", description="straight | L | U | stirrup | crank | ring")


class MemberResult(BaseModel):
    member_id: str
    kind: str
    tag: str
    nos: int
    size_label: str
    rows: List[BarRow]
    weight_kg: float
    weight_by_dia_kg: Dict[int, float]
    confidence: float
    warnings: List[str] = Field(default_factory=list)


class CategorySummary(BaseModel):
    category: str
    weight_by_dia_t: Dict[int, float]
    total_t: float
    member_count: int


class BBSSummary(BaseModel):
    level: str
    categories: List[CategorySummary]
    total_by_dia_t: Dict[int, float]
    grand_total_t: float


class BBSResult(BaseModel):
    standards: Standards
    members: List[MemberResult]
    summary: BBSSummary


# --------------------------------------------------------------------------- #
# Jobs / persistence
# --------------------------------------------------------------------------- #
class JobStatus(str, Enum):
    queued = "queued"
    converting = "converting"
    analysing = "analysing"
    extracting = "extracting"
    quantifying = "quantifying"
    ready = "ready"
    approved = "approved"
    failed = "failed"


class SourceFile(BaseModel):
    name: str
    size_bytes: int
    format: Literal["dwg", "dxf", "pdf", "image", "unknown"]
    storage_path: str
    mime: str = "application/octet-stream"


class SheetRecord(BaseModel):
    id: str
    job_id: str
    file_name: str
    page_no: int = 1
    layout: str = "Model"
    classification: SheetClassification
    preview_path: Optional[str] = None
    text_count: int = 0
    width: float = 0
    height: float = 0
    extraction: Optional[StructuralExtraction] = None
    fitout_extraction: Optional[FitoutExtraction] = None
    measurement_extraction: Optional["MeasurementExtraction"] = None
    processing_notes: List[str] = Field(default_factory=list)


class JobEvent(BaseModel):
    at: datetime
    status: JobStatus
    message: str
    progress: int = Field(0, ge=0, le=100)


class JobRecord(BaseModel):
    id: str
    module: Module = Module.measurement
    project_name: str
    level: str
    currency: str = Field("INR", description="Currency label for BOQ amounts")
    location: Optional[str] = None
    contractor: Optional[str] = None
    work_description: str = "Reinforcement For RCC Work Including Cutting, Bending, Placing In Position & Binding"
    drawn_by: Optional[str] = None
    drawing_refs: List[str] = Field(default_factory=list)
    status: JobStatus = JobStatus.queued
    progress: int = 0
    error: Optional[str] = None
    standards: Standards = Field(default_factory=Standards)
    source_files: List[SourceFile] = Field(default_factory=list)
    members: List[MemberSpec] = Field(default_factory=list)
    result: Optional[BBSResult] = None
    fitout_items: List[FitoutItem] = Field(default_factory=list)
    rooms: List[RoomRecord] = Field(default_factory=list)
    legend: Dict[str, str] = Field(default_factory=dict)
    boq: Optional[BOQResult] = None
    elements: Optional["MeasurementExtraction"] = None
    measurement: Optional["MeasurementResult"] = None
    general_notes: GeneralNotes = Field(default_factory=GeneralNotes)
    sheet_count: int = 0
    events: List[JobEvent] = Field(default_factory=list)
    created_by: Optional[str] = None
    created_by_email: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    export_path: Optional[str] = None
    export_version: int = 0


class JobSummaryRecord(BaseModel):
    """Light version for lists."""
    id: str
    module: Module = Module.measurement
    project_name: str
    level: str
    status: JobStatus
    progress: int
    created_at: datetime
    updated_at: datetime
    created_by_email: Optional[str] = None
    member_count: int = Field(0, description="BBS members or BOQ lines")
    grand_total_t: Optional[float] = Field(None, description="Structural: steel in tons")
    grand_total_amount: Optional[float] = Field(None, description="Fit-out: priced amount if rates entered")
    headline: str = Field("", description="Ready-made label e.g. '41.2 t steel' or '63 items / 1,240 m2'")
    file_names: List[str] = Field(default_factory=list)


class CreateJobResponse(BaseModel):
    job_id: str
    status: JobStatus


class MemberUpdate(BaseModel):
    """Partial update of a member's extracted inputs by a reviewer."""
    member: Dict[str, Any]


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    role: Literal["engineer", "reviewer", "admin"] = "engineer"
    must_set_password: bool = False
    is_active: bool = True
    created_at: Optional[datetime] = None
    last_sign_in_at: Optional[datetime] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    profile: UserProfile


class SetPasswordRequest(BaseModel):
    password: str = Field(min_length=8)
    current_password: Optional[str] = None


class ItemUpdate(BaseModel):
    """Partial update of a fit-out BOQ item by a reviewer."""
    item: Dict[str, Any]


class AIStatus(BaseModel):
    enabled: bool
    provider: str = "gemini"
    model_fast: Optional[str] = None
    model_pro: Optional[str] = None
    message: str = ""


class InviteRequest(BaseModel):
    email: str
    full_name: Optional[str] = None
    role: Literal["engineer", "reviewer", "admin"] = "engineer"
    temporary_password: Optional[str] = Field(None, description="If omitted the server generates one and returns it once")


class InviteResponse(BaseModel):
    profile: UserProfile
    temporary_password: str


class RoleUpdate(BaseModel):
    role: Optional[Literal["engineer", "reviewer", "admin"]] = None
    is_active: Optional[bool] = None
    full_name: Optional[str] = None


# =========================================================================== #
# MEASUREMENT module (the product): drawing -> elements -> measurement sheet
# -> BOQ abstract -> material requirement. Lengths in metres.
# =========================================================================== #
WallType = Literal["rcc", "block", "partition", "glass", "other"]
OpeningKind = Literal["door", "window", "opening", "ventilator"]


class RoomEl(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str = Field(description="Room / space name e.g. Bedroom 1, Living, Toilet 2")
    level: str = Field("", description="Floor / level e.g. 6th floor")
    length_m: float = Field(gt=0, description="Internal clear length")
    width_m: float = Field(gt=0, description="Internal clear width")
    height_m: float = Field(3.0, gt=0, description="Floor to ceiling height")
    area_m2: Optional[float] = Field(None, description="Measured area when the room is not rectangular")
    perimeter_m: Optional[float] = Field(None, description="Measured perimeter when not rectangular")
    floor_finish: str = Field("Vitrified tile flooring 600x600", description="Floor finish description / code")
    wall_finish: str = Field("Putty + primer + emulsion", description="Wall finish (paint / tiles / wallpaper)")
    ceiling_finish: str = Field("Putty + primer + emulsion", description="Ceiling finish")
    skirting_mm: float = Field(100, ge=0, description="Skirting height, 0 = none")
    dado_height_m: float = Field(0, ge=0, description="Wall tile (dado) height, 0 = none")
    wet_area: bool = Field(False, description="Bathroom / kitchen / utility -> waterproofing")
    plastered: bool = Field(True, description="Walls need plaster (False for Mivan RCC walls: putty only)")
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)
    source_sheet: Optional[str] = None
    remarks: Optional[str] = None


class OpeningEl(BaseModel):
    id: str = Field(default_factory=new_id)
    tag: str = Field(description="D1, W2, V1 ...")
    kind: OpeningKind = "door"
    width_m: float = Field(gt=0)
    height_m: float = Field(gt=0)
    count: int = Field(1, ge=1)
    room: str = Field("", description="Room the opening belongs to")
    wall_tag: str = Field("", description="Wall it sits in, if known")
    description: str = Field("", description="e.g. Flush door 35 mm with frame & hardware")
    level: str = ""
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)
    source_sheet: Optional[str] = None


class WallEl(BaseModel):
    id: str = Field(default_factory=new_id)
    tag: str = Field(description="W1, W2 ...")
    wall_type: WallType = "block"
    length_m: float = Field(gt=0)
    thickness_m: float = Field(gt=0)
    height_m: float = Field(gt=0)
    count: int = Field(1, ge=1)
    room: str = ""
    level: str = ""
    both_faces: bool = Field(True, description="Formwork / finish on both faces")
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)
    source_sheet: Optional[str] = None


class SlabEl(BaseModel):
    id: str = Field(default_factory=new_id)
    tag: str = "S1"
    length_m: float = Field(gt=0)
    width_m: float = Field(gt=0)
    thickness_m: float = Field(0.15, gt=0)
    count: int = Field(1, ge=1)
    level: str = ""
    beam_width_m: float = Field(0.23, ge=0, description="Beam width to subtract from soffit formwork")
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)
    source_sheet: Optional[str] = None


class MemberEl(BaseModel):
    """Column or beam."""
    id: str = Field(default_factory=new_id)
    tag: str
    kind: Literal["column", "beam"] = "column"
    width_m: float = Field(gt=0)
    depth_m: float = Field(gt=0)
    length_m: float = Field(gt=0, description="Height for columns, clear span for beams")
    count: int = Field(1, ge=1)
    level: str = ""
    slab_thickness_m: float = Field(0, ge=0, description="Beams: slab thickness included in depth (measured below slab)")
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)
    source_sheet: Optional[str] = None


class MiscEl(BaseModel):
    """Anything countable that is not a room/wall/opening: fixtures, joinery, lights, sanitary ware..."""
    id: str = Field(default_factory=new_id)
    tag: Optional[str] = None
    description: str
    unit: Literal["nos", "sqm", "rmt", "cum", "kg", "LS"] = "nos"
    qty: float = Field(gt=0)
    trade: str = Field("Miscellaneous", description="Plumbing / Electrical / Joinery / Sanitary / Other")
    room: str = ""
    level: str = ""
    confidence: float = 0.5
    evidence: List[str] = Field(default_factory=list)
    source_sheet: Optional[str] = None


class ProjectAssumptions(BaseModel):
    floor_height_m: float = 3.0
    wall_thickness_m: float = 0.2
    slab_thickness_m: float = 0.15
    construction: Literal["mivan", "conventional"] = "conventional"
    concrete_grade: str = "M40"
    notes: List[str] = Field(default_factory=list)


class MeasurementExtraction(BaseModel):
    rooms: List[RoomEl] = Field(default_factory=list)
    openings: List[OpeningEl] = Field(default_factory=list)
    walls: List[WallEl] = Field(default_factory=list)
    slabs: List[SlabEl] = Field(default_factory=list)
    members: List[MemberEl] = Field(default_factory=list)
    misc: List[MiscEl] = Field(default_factory=list)
    assumptions: ProjectAssumptions = Field(default_factory=ProjectAssumptions)
    warnings: List[str] = Field(default_factory=list)

    def count(self) -> int:
        return len(self.rooms) + len(self.openings) + len(self.walls) + len(self.slabs) + len(self.members) + len(self.misc)


# ---- results
class MeasurementRow(BaseModel):
    sr: int
    location: str = Field(description="What & where: 'Wall W1 (outer), Bedroom 1, 6th floor'")
    nos: float = 1
    l_m: Optional[float] = None
    b_m: Optional[float] = None
    h_m: Optional[float] = None
    qty: float
    deduction: bool = False
    rule: str = Field("", description="IS 1200 rule / drawing reference")
    element_id: Optional[str] = None
    room_id: Optional[str] = Field(None, description="Room this row belongs to (None = common / whole floor)")


class MeasurementBlock(BaseModel):
    item_code: str
    item_title: str
    unit: str
    trade: str
    rows: List[MeasurementRow]
    total: float


class BOQAbstractLine(BaseModel):
    item_no: int
    item_code: str
    trade: str
    description: str
    unit: str
    qty: float
    rate: Optional[float] = None
    amount: Optional[float] = None
    basis: Literal["measured", "thumb_rule", "manual"] = "measured"


class MaterialRow(BaseModel):
    material: str
    for_item_code: str
    boq_qty: float
    boq_unit: str
    norm: float
    norm_unit: str
    wastage_pct: float
    required: float
    basis: str = ""


class RoomItemLine(BaseModel):
    """One work item inside one room (or in the common section): the room's share of a BOQ item."""
    item_code: str
    item_title: str
    trade: str
    unit: str
    qty: float


class RoomOpeningLine(BaseModel):
    tag: str
    kind: str
    width_m: float
    height_m: float
    count: float
    description: str = ""


class RoomMiscLine(BaseModel):
    description: str
    qty: float
    unit: str
    trade: str
    tag: str = ""


class MaterialTotal(BaseModel):
    material: str
    required: float
    unit: str


class RoomBreakdown(BaseModel):
    """Everything that belongs to one room: size, finishes, its work items, openings, other items and the
    materials those items need. `room_id` None = the common / whole-floor section (RCC, slabs, members,
    items whose room is not known)."""
    room_id: Optional[str] = None
    name: str
    level: str = ""
    length_m: float = 0
    width_m: float = 0
    height_m: float = 0
    area_m2: float = 0
    perimeter_m: float = 0
    floor_finish: str = ""
    wall_finish: str = ""
    ceiling_finish: str = ""
    wet_area: bool = False
    items: List[RoomItemLine] = Field(default_factory=list)
    openings: List[RoomOpeningLine] = Field(default_factory=list)
    misc: List[RoomMiscLine] = Field(default_factory=list)
    materials: List[MaterialRow] = Field(default_factory=list)
    material_totals: List[MaterialTotal] = Field(default_factory=list)
    totals_by_trade: Dict[str, Dict[str, float]] = Field(default_factory=dict)


class MeasurementResult(BaseModel):
    blocks: List[MeasurementBlock]
    boq: List[BOQAbstractLine]
    materials: List[MaterialRow]
    totals_by_trade: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    room_breakdown: List[RoomBreakdown] = Field(default_factory=list, description="One entry per room")
    common_breakdown: Optional[RoomBreakdown] = Field(None, description="Items not tied to one room (whole floor)")


class ElementsUpdate(BaseModel):
    """Whole element set after reviewer edits (PUT /jobs/{id}/elements)."""
    elements: MeasurementExtraction


JobRecord.model_rebuild()
SheetRecord.model_rebuild()
ElementsUpdate.model_rebuild()
