"""Per-consultant configuration for the structural DXF reader.

Every structural consultant draws with their own layer names and label style, so the
reader is driven by this config. The defaults below match Mahimtura Consultants
(Nishika Elysium). A new consultant needs a one-time setup here, not new code.
All lengths are DXF drawing units, assumed millimetres.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class StructuralConfig:
    # Layers that hold the beam edge lines. Only entities whose colour is the layer
    # colour (ACI 256 = BYLAYER) or beam_line_aci count as beam edges; other colours
    # on the same layer are annotation (dimension ticks etc.).
    beam_line_layers: Tuple[str, ...] = ("BEAM",)
    beam_line_aci: Tuple[int, ...] = (256, 2)
    # Layers whose lines close slab panels together with the beam lines.
    slab_line_layers: Tuple[str, ...] = ("SLAB",)
    # Column / wall hatches.
    column_hatch_layers: Tuple[str, ...] = ("column hatch", "COL HATCH")
    # ACI colours that mean "hanging column" (trims a beam end but does not cut it).
    hanging_column_aci: Tuple[int, ...] = (0, 7, 250)
    floating_column_aci: Tuple[int, ...] = (6,)
    # Text layers.
    beam_tag_layers: Tuple[str, ...] = ("BEAM NO.",)
    beam_size_layers: Tuple[str, ...] = ("BEAM SIZES",)
    column_tag_layers: Tuple[str, ...] = ("S-COLS-NUM",)
    column_size_layers: Tuple[str, ...] = ("COLUMN SIZE",)
    # Slab tags often live on a shared text layer; matched by pattern.
    slab_tag_layers: Tuple[str, ...] = ("COLUMN SIZE", "SLAB", "slab dire")
    note_layers: Tuple[str, ...] = ("TEXT1", "Text", "slab dire", "sunk", "SLAB")
    # Default (U.N.O. — "unless noted otherwise") beam size in mm, from the notes.
    default_beam_size: Tuple[int, int] = (230, 750)
    default_slab_thickness_mm: int = 150
    # Tolerances, all in mm.
    node_tol: float = 25.0          # beam edge lines joined end-to-end within this
    width_tol: float = 20.0         # partner line must sit at schedule width +/- this
    min_beam_len: float = 300.0     # never produce a beam piece shorter than this
    # Optional explicit plan region [x0, y0, x1, y1]; None = auto-detect from the
    # largest cluster of column hatches (handles loose duplicate plans in the file).
    plan_region: Optional[List[float]] = None
    # Candidate widths tried when the drawn width disagrees with the schedule.
    loose_widths: Tuple[int, ...] = (160, 200, 230, 300)

    def __post_init__(self) -> None:
        self.beam_line_layers = tuple(self.beam_line_layers)
        self.slab_line_layers = tuple(self.slab_line_layers)


DEFAULT_CONFIG = StructuralConfig()
