"""Generate a realistic sample structural sheet (beam + column schedule) for demos and tests.
Usage: PYTHONPATH=. python3 tools/make_sample_structural_pdf.py samples/sample_beam_schedule_14th_floor.pdf
"""
from __future__ import annotations

import sys
from pathlib import Path

import fitz

BEAMS = [
    # tag, nos, size, span(mm), bottom, top, left extra, right extra, stirrups end, stirrups mid
    ("B1", 1, "230x750", 2450, "2-T20", "2-T20", "-", "-", "T8@100", "T8@150"),
    ("B2", 2, "300x425", 2705, "3-T12", "2-T12", "1-T12", "1-T12", "T8@100", "T8@150"),
    ("B3", 1, "230x600", 4200, "3-T16", "2-T16", "2-T16", "2-T16", "T8@100", "T8@150"),
    ("B4", 1, "230x600", 3850, "3-T16", "2-T12", "1-T16", "1-T16", "T8@100", "T8@175"),
    ("B5", 2, "230x450", 3100, "2-T16", "2-T12", "-", "1-T12", "T8@125", "T8@175"),
    ("B6", 1, "300x750", 5600, "4-T20", "3-T16", "2-T20", "2-T20", "T10@100", "T10@150"),
    ("B7", 1, "230x450", 2800, "2-T12", "2-T12", "-", "-", "T8@150", "T8@150"),
    ("B8", 3, "230x600", 4500, "3-T16", "2-T16", "2-T16", "1-T16", "T8@100", "T8@150"),
]
COLUMNS = [
    ("C1", 4, "300x600", "8-T16", "T8@100", "T8@250"),
    ("C2", 2, "300x900", "12-T20", "T8@100", "T8@200"),
    ("C3", 6, "230x600", "6-T16", "T8@100", "T8@250"),
    ("C4", 2, "450x450", "8-T20", "T8@100", "T8@200"),
]


def main(out: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=1684, height=1190)  # A2 landscape in points
    fs_title, fs = 20, 11
    page.insert_text((50, 50), "NISHIKA ELYSIUM (AVIGHNA) - 14TH FLOOR BEAM & COLUMN SCHEDULE", fontsize=fs_title, fontname="helv")
    page.insert_text((50, 75), "DWG NO 9680/P.P/13   SCALE 1:50   LEVEL 14TH FLOOR   CONTRACTOR: MEHTA JAISING BUILDERS LLP", fontsize=fs, fontname="helv")
    page.insert_text((50, 95), "GENERAL NOTES: CONCRETE GRADE M40, STEEL Fe500D. CLEAR COVER BEAM 30, SLAB 20, COLUMN 40. LAP LENGTH Ld = 39d. ALL DIMENSIONS IN MM.", fontsize=fs, fontname="helv")
    # beam schedule table
    cols = ["BEAM", "NOS", "SIZE (BxD)", "SPAN", "BOTTOM", "TOP", "LEFT EXTRA", "RIGHT EXTRA", "STIRRUPS ENDS (L/3)", "STIRRUPS MID"]
    xs = [50, 130, 190, 300, 380, 470, 560, 670, 780, 940]
    y = 140
    page.insert_text((50, y - 20), "BEAM SCHEDULE", fontsize=14, fontname="helv")
    for x, c in zip(xs, cols):
        page.insert_text((x, y), c, fontsize=fs, fontname="helv")
    page.draw_line((50, y + 5), (1080, y + 5))
    for row in BEAMS:
        y += 24
        tag, nos, size, span, bot, top, lx, rx, se, sm = row
        vals = [f"{tag} ({nos} nos)" if nos > 1 else tag, str(nos), size, str(span), bot, top, lx, rx, se + " c/c", sm + " c/c"]
        for x, v in zip(xs, vals):
            page.insert_text((x, y), v, fontsize=fs, fontname="helv")
    # column schedule table
    y += 60
    page.insert_text((50, y - 20), "COLUMN SCHEDULE (13TH TO 14TH FLOOR, FLOOR HEIGHT 3800)", fontsize=14, fontname="helv")
    ccols = ["COLUMN", "NOS", "SIZE", "VERTICAL BARS", "MAIN RING", "INNER TIES"]
    cxs = [50, 150, 210, 320, 450, 580]
    for x, c in zip(cxs, ccols):
        page.insert_text((x, y), c, fontsize=fs, fontname="helv")
    page.draw_line((50, y + 5), (700, y + 5))
    for tag, nos, size, bars, ring, tie in COLUMNS:
        y += 24
        vals = [f"{tag} ({nos} nos)", str(nos), size, bars, ring + " c/c", tie + " c/c"]
        for x, v in zip(cxs, vals):
            page.insert_text((x, y), v, fontsize=fs, fontname="helv")
    # title block
    page.draw_rect(fitz.Rect(1300, 1000, 1660, 1160), width=1)
    for i, line in enumerate(["AVIGHNA GROUP", "PROJECT: NISHIKA ELYSIUM, WORLI", "DRAWING: 14TH FLOOR BEAM & COLUMN SCHEDULE",
                              "DRAWING NO: 9680/P.P/13   REV: 1", "SCALE 1:50   DATE: 10.10.2026", "DRAWN BY: MUSHARRAF"]):
        page.insert_text((1310, 1025 + i * 22), line, fontsize=10, fontname="helv")
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    print("wrote", out, page.rect)


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "samples/sample_beam_schedule_14th_floor.pdf"))
