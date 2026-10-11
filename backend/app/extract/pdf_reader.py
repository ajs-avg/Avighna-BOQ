"""Read vector/scanned PDFs with PyMuPDF into SheetInventory objects (one per page) + previews."""
from __future__ import annotations

import logging
import re
from collections import Counter
from pathlib import Path
from typing import List

import fitz  # PyMuPDF

from app.extract.inventory import SheetInventory, TextItem, guess_units

log = logging.getLogger(__name__)


def read_pdf(path: Path, max_pages: int = 400) -> List[SheetInventory]:
    doc = fitz.open(str(path))
    layers: List[str] = []
    try:
        layers = sorted({(v.get("name") or "") for v in doc.get_ocgs().values()} - {""})
    except Exception:
        pass
    out: List[SheetInventory] = []
    for pno, page in enumerate(doc):
        if pno >= max_pages:
            break
        rect = page.rect
        inv = SheetInventory(source=path.name, page_no=pno + 1, layout=f"Page {pno + 1}",
                             width=float(rect.width), height=float(rect.height), units_hint="unknown")
        inv.layers = layers
        try:
            d = page.get_text("dict")
        except Exception as exc:
            inv.notes.append(f"text extraction failed: {exc}")
            d = {"blocks": []}
        for b in d.get("blocks", []):
            for line in b.get("lines", []):
                dirx, diry = line.get("dir", (1, 0))
                rot = 0.0 if abs(dirx) >= abs(diry) else 90.0
                for s in line.get("spans", []):
                    t = (s.get("text") or "").strip()
                    if not t:
                        continue
                    x0, y0, x1, y1 = s["bbox"]
                    # flip y so that y points up like DXF
                    inv.add(TextItem(t, float(x0), float(rect.height - y1), float(x1 - x0), float(y1 - y0),
                                     "", "text", rot))
        try:
            drawings = page.get_drawings()
            inv.entity_counts = dict(Counter("path" for _ in drawings))
            inv.entity_counts["images"] = len(page.get_images())
            inv.entity_counts["text"] = len(inv.texts)
        except Exception:
            pass
        inv.units_hint = guess_units(inv)
        if not inv.texts and page.get_images():
            inv.notes.append("scanned page: no machine-readable text, vision model required")
        out.append(inv)
    doc.close()
    return out


def render_page_png(path: Path, page_no: int = 1, max_px: int = 3000, dpi: int = 110) -> bytes:
    doc = fitz.open(str(path))
    page = doc[page_no - 1]
    rect = page.rect
    scale = dpi / 72.0
    if max(rect.width, rect.height) * scale > max_px:
        scale = max_px / max(rect.width, rect.height)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    png = pix.tobytes("png")
    doc.close()
    return png


def render_region_png(path: Path, page_no: int, bbox_norm: tuple, max_px: int = 2000) -> bytes:
    """Crop a region given in normalised 0-1000 coords (x0,y0,x1,y1 with y=0 at top)."""
    doc = fitz.open(str(path))
    page = doc[page_no - 1]
    r = page.rect
    x0, y0, x1, y1 = bbox_norm
    clip = fitz.Rect(r.width * x0 / 1000, r.height * y0 / 1000, r.width * x1 / 1000, r.height * y1 / 1000)
    scale = min(max_px / max(clip.width, 1), max_px / max(clip.height, 1), 6.0)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
    png = pix.tobytes("png")
    doc.close()
    return png


TITLE_KEYS = re.compile(r"(drawing\s*no|dwg\.?\s*no|sheet\s*no|title|scale|level|floor|project|client|rev)", re.I)


def title_block_hints(inv: SheetInventory) -> List[str]:
    """Texts that look like title-block content (bottom-right 30% of the sheet)."""
    if not inv.texts or not inv.width or not inv.height:
        return []
    hints = []
    for t in inv.texts:
        in_corner = t.x > inv.width * 0.7 or t.y < inv.height * 0.2
        if in_corner or TITLE_KEYS.search(t.text):
            hints.append(t.text)
    return hints[:150]
