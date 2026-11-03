"""Structural DXF reader.

Reads a structural floor plan directly from the CAD geometry instead of asking the
AI to look at a picture: exact text entities for names and sizes, column hatches for
columns/walls, chained beam edge lines for beams (straight, angled and curved), the
beam schedule on the sheet as a second source for sizes, closed regions between
beams for slab panels, and crossed-out / "NOT TO REFER" areas skipped.

Validated on Nishika Elysium 14th floor (Mahimtura 9680/P.P/16 R2): 30/30
columns+walls, 78/78 beam names and sizes, 69/78 beam lengths, 42/42 slab labels
against the contractor's measurement sheet.
"""
from app.extract.structural.config import StructuralConfig
from app.extract.structural.reader import StructuralReadResult, read_structural_dxf, structural_to_measurement

__all__ = ["StructuralConfig", "StructuralReadResult", "read_structural_dxf", "structural_to_measurement"]
