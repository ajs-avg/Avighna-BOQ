"""Excel writer for the measurement module: 4 tabs exactly like the agreed sample
(Measurement Sheet with item blocks + formulas, BOQ abstract linked to totals, Material
Requirement, Tender vs Site template)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.engine.measurement import material_totals
from app.models.schemas import JobRecord

RED, INK, MUTED = "ED1C24", "231F20", "6B6B70"
H = Font(bold=True, color="FFFFFF", name="Arial", size=10)
HF = PatternFill("solid", fgColor=RED)
B = Font(bold=True, name="Arial", size=10, color=INK)
N = Font(name="Arial", size=10, color=INK)
ITEM = Font(bold=True, name="Arial", size=10, color=RED)
NOTE = Font(italic=True, name="Arial", size=9, color=MUTED)
thin = Side(style="thin", color="C9C9CE")
BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
TOT = PatternFill("solid", fgColor="FDECED")
DED = PatternFill("solid", fgColor="F7F7F8")


def _header(ws, row: int, cols: List[str], widths: List[int]) -> None:
    for i, (c, w) in enumerate(zip(cols, widths), 1):
        cell = ws.cell(row=row, column=i, value=c)
        cell.font, cell.fill, cell.border = H, HF, BOX
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[row].height = 28


def _title(ws, text: str, sub: str) -> None:
    ws["A1"] = text
    ws["A1"].font = Font(bold=True, size=13, name="Arial", color=RED)
    ws["A2"] = sub
    ws["A2"].font = NOTE


def _cell(ws, r: int, c: int, v, font=N, fill=None, fmt=None, wrap=False):
    cell = ws.cell(row=r, column=c, value=v)
    cell.font, cell.border = font, BOX
    cell.alignment = Alignment(vertical="top", wrap_text=wrap)
    if fill:
        cell.fill = fill
    if fmt:
        cell.number_format = fmt
    return cell


def _setup_print(ws) -> None:
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def write_measurement_workbook(job: JobRecord, path: Path) -> Path:
    res = job.measurement
    if res is None:
        raise ValueError("job has no measurement result")
    wb = Workbook()
    wb.properties.creator = "Avighna BOQ"
    head = f"{job.project_name} — {job.level}" + (f" — {job.location}" if job.location else "")

    # ------------------------------------------------------------------ 1. Measurement sheet
    ws = wb.active
    ws.title = "Measurement Sheet"
    _title(ws, f"MEASUREMENT SHEET — {head}", "Har row = Nos × L × B × H. Deductions minus rows (IS 1200). Totals → BOQ tab. Drawings: " + ", ".join(job.drawing_refs[:6]))
    _header(ws, 4, ["Sr", "Location (kya, kahan)", "No.", "L (m)", "B (m)", "H (m)", "Qty", "Unit", "Rule / drawing ref"], [5, 50, 7, 8, 8, 8, 11, 7, 40])
    r = 5
    total_cells: Dict[str, str] = {}
    for b in res.blocks:
        ws.cell(row=r, column=1, value=b.item_code).font = ITEM
        ws.cell(row=r, column=2, value=b.item_title).font = ITEM
        r += 1
        first = r
        for row in b.rows:
            parts = [f"C{r}"] + [f"{col}{r}" for col, v in zip(("D", "E", "F"), (row.l_m, row.b_m, row.h_m)) if v is not None]
            if any(v is not None for v in (row.l_m, row.b_m, row.h_m)):
                qty = "=" + "*".join(parts)
            else:
                qty = row.qty  # pre-computed (areas from CAD, thumb rules)
            fill = DED if row.deduction else None
            _cell(ws, r, 1, row.sr, fill=fill)
            _cell(ws, r, 2, row.location, fill=fill, wrap=True)
            _cell(ws, r, 3, row.nos, fill=fill, fmt="0.##")
            _cell(ws, r, 4, row.l_m, fill=fill, fmt="0.00")
            _cell(ws, r, 5, row.b_m, fill=fill, fmt="0.00")
            _cell(ws, r, 6, row.h_m, fill=fill, fmt="0.00")
            _cell(ws, r, 7, qty, fill=fill, fmt="0.000")
            _cell(ws, r, 8, b.unit, fill=fill)
            _cell(ws, r, 9, row.rule, fill=fill, wrap=True)
            r += 1
        _cell(ws, r, 1, "", font=B, fill=TOT)
        _cell(ws, r, 2, f"Total — {b.item_code}", font=B, fill=TOT)
        for c in range(3, 7):
            _cell(ws, r, c, None, font=B, fill=TOT)
        _cell(ws, r, 7, f"=SUM(G{first}:G{r-1})", font=B, fill=TOT, fmt="0.000")
        _cell(ws, r, 8, b.unit, font=B, fill=TOT)
        _cell(ws, r, 9, "→ BOQ", font=B, fill=TOT)
        total_cells[b.item_code] = f"'Measurement Sheet'!G{r}"
        r += 2
    ws.freeze_panes = "A5"
    _setup_print(ws)

    # ------------------------------------------------------------------ 2. BOQ abstract
    bq = wb.create_sheet("BOQ (Abstract)")
    _title(bq, f"BILL OF QUANTITIES (abstract) — {head}", "Ek item = ek line. Qty measurement sheet ke Total se linked. Rate khaali (pricing nahi).")
    _header(bq, 4, ["Item", "Description (kya kaam, kaunsi quality, kya included)", "Qty", "Unit", f"Rate ({job.currency})", f"Amount ({job.currency})", "Basis"], [6, 80, 11, 7, 11, 13, 12])
    r = 5
    current_trade = None
    first_amt = r
    for line in res.boq:
        if line.trade != current_trade:
            current_trade = line.trade
            for c in range(1, 8):
                _cell(bq, r, c, None, font=ITEM)
            bq.cell(row=r, column=2, value=current_trade.upper()).font = ITEM
            r += 1
        _cell(bq, r, 1, line.item_no)
        _cell(bq, r, 2, line.description, wrap=True)
        _cell(bq, r, 3, "=" + total_cells.get(line.item_code, str(line.qty)), fmt="0.00")
        _cell(bq, r, 4, line.unit)
        _cell(bq, r, 5, line.rate, fmt="#,##0.00")
        _cell(bq, r, 6, f"=C{r}*E{r}", fmt="#,##0")
        _cell(bq, r, 7, "thumb rule" if line.basis == "thumb_rule" else "measured", font=NOTE if line.basis == "thumb_rule" else N)
        r += 1
    _cell(bq, r, 2, "Total (excluding GST)", font=B)
    _cell(bq, r, 6, f"=SUM(F{first_amt}:F{r-1})", font=B, fmt="#,##0")
    r += 1
    _cell(bq, r, 2, "GST @ 18%", font=N)
    _cell(bq, r, 6, f"=ROUND(F{r-1}*18/100,0)", fmt="#,##0")
    r += 1
    _cell(bq, r, 2, "Grand total", font=B)
    _cell(bq, r, 6, f"=F{r-2}+F{r-1}", font=B, fmt="#,##0")
    bq.freeze_panes = "A5"
    _setup_print(bq)

    # ------------------------------------------------------------------ 3. Material requirement
    mt = wb.create_sheet("Material Requirement")
    _title(mt, f"MATERIAL REQUIREMENT — {head}", "Required = BOQ qty × norm × (1 + wastage). Norms editable in Standards.")
    _header(mt, 4, ["Material", "For item", "BOQ qty", "Unit", "Norm per unit", "Wastage %", "Required", "Material unit", "Basis"], [34, 12, 10, 7, 13, 10, 12, 12, 36])
    boq_row_for: Dict[str, int] = {}
    # find BOQ rows for cross-links
    rr = 5
    for line in res.boq:
        pass
    r = 5
    for m in res.materials:
        _cell(mt, r, 1, m.material)
        _cell(mt, r, 2, m.for_item_code)
        _cell(mt, r, 3, "=" + total_cells.get(m.for_item_code, str(m.boq_qty)), fmt="0.00")
        _cell(mt, r, 4, m.boq_unit)
        _cell(mt, r, 5, m.norm, fmt="0.####")
        _cell(mt, r, 6, m.wastage_pct, fmt="0.#")
        _cell(mt, r, 7, f"=C{r}*E{r}*(1+F{r}/100)", font=B, fmt="0.0")
        _cell(mt, r, 8, m.norm_unit)
        _cell(mt, r, 9, m.basis, wrap=True)
        r += 1
    r += 1
    mt.cell(row=r, column=1, value="SUMMARY BY MATERIAL (all items)").font = ITEM
    r += 1
    _header(mt, r, ["Material", "", "", "", "", "", "Total required", "Unit", ""], [34, 12, 10, 7, 13, 10, 12, 12, 36])
    r += 1
    for name, (q, u) in material_totals(res.materials).items():
        _cell(mt, r, 1, name, font=B)
        _cell(mt, r, 7, q, font=B, fmt="0.0")
        _cell(mt, r, 8, u)
        r += 1
    mt.freeze_panes = "A5"
    _setup_print(mt)

    # ------------------------------------------------------------------ 4. Tender vs site
    sv = wb.create_sheet("Tender vs Site")
    _title(sv, f"TENDER BOQ vs SITE MEASUREMENT — {head}", "Rate contract se fixed; quantity site se. Site qty column site engineer bharega (measurement book).")
    _header(sv, 4, ["Item", "Description", "Tender qty", "Site qty", "Unit", "Variation", "Variation %", f"Rate ({job.currency})", "Tender amt", "Bill amt"], [6, 60, 11, 11, 7, 11, 11, 11, 13, 13])
    r = 5
    for line in res.boq:
        _cell(sv, r, 1, line.item_no)
        _cell(sv, r, 2, line.description, wrap=True)
        _cell(sv, r, 3, "=" + total_cells.get(line.item_code, str(line.qty)), fmt="0.00")
        _cell(sv, r, 4, None, fmt="0.00")
        _cell(sv, r, 5, line.unit)
        _cell(sv, r, 6, f"=IF(D{r}=\"\",\"\",D{r}-C{r})", fmt="0.00")
        _cell(sv, r, 7, f"=IF(OR(D{r}=\"\",C{r}=0),\"\",(D{r}-C{r})/C{r})", fmt="0.0%")
        _cell(sv, r, 8, line.rate, fmt="#,##0.00")
        _cell(sv, r, 9, f"=C{r}*H{r}", fmt="#,##0")
        _cell(sv, r, 10, f"=IF(D{r}=\"\",\"\",D{r}*H{r})", fmt="#,##0")
        r += 1
    sv.freeze_panes = "A5"
    _setup_print(sv)

    # ------------------------------------------------------------------ 5. Elements read (audit)
    el = wb.create_sheet("Elements (from drawing)")
    _title(el, "ELEMENTS READ FROM THE DRAWINGS — audit", "Jo AI/geometry ne padha. Confidence kam ho to drawing se check karein.")
    _header(el, 4, ["Type", "Tag / name", "Level", "Size (m)", "Count", "Finishes / notes", "Confidence", "Evidence", "Sheet"], [10, 22, 12, 22, 7, 44, 10, 50, 28])
    r = 5
    ex = job.elements
    if ex is not None:
        for x in ex.rooms:
            _cell(el, r, 1, "Room"); _cell(el, r, 2, x.name); _cell(el, r, 3, x.level)
            _cell(el, r, 4, f"{x.length_m:.2f} x {x.width_m:.2f} x H {x.height_m:.2f}" + (f" (area {x.area_m2:.2f})" if x.area_m2 else ""))
            _cell(el, r, 5, 1); _cell(el, r, 6, f"floor: {x.floor_finish}; walls: {x.wall_finish}; ceiling: {x.ceiling_finish}" + ("; wet area" if x.wet_area else ""), wrap=True)
            _cell(el, r, 7, x.confidence, fmt="0%"); _cell(el, r, 8, " | ".join(x.evidence)[:400], wrap=True); _cell(el, r, 9, x.source_sheet)
            r += 1
        for x in ex.openings:
            _cell(el, r, 1, x.kind.title()); _cell(el, r, 2, x.tag); _cell(el, r, 3, x.level); _cell(el, r, 4, f"{x.width_m:.2f} x {x.height_m:.2f}")
            _cell(el, r, 5, x.count); _cell(el, r, 6, f"{x.description}; room: {x.room}; wall: {x.wall_tag}", wrap=True)
            _cell(el, r, 7, x.confidence, fmt="0%"); _cell(el, r, 8, " | ".join(x.evidence)[:400], wrap=True); _cell(el, r, 9, x.source_sheet)
            r += 1
        for x in ex.walls:
            _cell(el, r, 1, "Wall"); _cell(el, r, 2, x.tag); _cell(el, r, 3, x.level); _cell(el, r, 4, f"{x.length_m:.2f} x {x.thickness_m:.2f} x H {x.height_m:.2f}")
            _cell(el, r, 5, x.count); _cell(el, r, 6, f"{x.wall_type}; room: {x.room}", wrap=True)
            _cell(el, r, 7, x.confidence, fmt="0%"); _cell(el, r, 8, " | ".join(x.evidence)[:400], wrap=True); _cell(el, r, 9, x.source_sheet)
            r += 1
        for x in ex.slabs:
            _cell(el, r, 1, "Slab"); _cell(el, r, 2, x.tag); _cell(el, r, 3, x.level); _cell(el, r, 4, f"{x.length_m:.2f} x {x.width_m:.2f} x {x.thickness_m:.3f}")
            _cell(el, r, 5, x.count); _cell(el, r, 6, ""); _cell(el, r, 7, x.confidence, fmt="0%"); _cell(el, r, 8, " | ".join(x.evidence)[:400], wrap=True); _cell(el, r, 9, x.source_sheet)
            r += 1
        for x in ex.members:
            _cell(el, r, 1, x.kind.title()); _cell(el, r, 2, x.tag); _cell(el, r, 3, x.level); _cell(el, r, 4, f"{x.width_m:.2f} x {x.depth_m:.2f} x L {x.length_m:.2f}")
            _cell(el, r, 5, x.count); _cell(el, r, 6, ""); _cell(el, r, 7, x.confidence, fmt="0%"); _cell(el, r, 8, " | ".join(x.evidence)[:400], wrap=True); _cell(el, r, 9, x.source_sheet)
            r += 1
        for x in ex.misc:
            _cell(el, r, 1, "Item"); _cell(el, r, 2, x.tag or ""); _cell(el, r, 3, x.level); _cell(el, r, 4, f"{x.qty:g} {x.unit}")
            _cell(el, r, 5, ""); _cell(el, r, 6, f"{x.trade}: {x.description}; room: {x.room}", wrap=True)
            _cell(el, r, 7, x.confidence, fmt="0%"); _cell(el, r, 8, " | ".join(x.evidence)[:400], wrap=True); _cell(el, r, 9, x.source_sheet)
            r += 1
        r += 1
        a = ex.assumptions
        el.cell(row=r, column=1, value=f"Assumptions: floor height {a.floor_height_m} m, wall thk {a.wall_thickness_m} m, slab {a.slab_thickness_m} m, {a.construction}, {a.concrete_grade}. " + " ".join(a.notes)).font = NOTE
    for w_ in res.warnings:
        r += 1
        el.cell(row=r, column=1, value="Warning: " + w_).font = NOTE
    el.freeze_panes = "A5"
    _setup_print(el)
    el.cell(row=2, column=9, value=f"Generated by Avighna BOQ on {datetime.utcnow():%d-%b-%Y}").font = NOTE

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(path))
    return path
