"""Raster drawings (PNG/JPG/TIFF/scans): normalise to PNG, keep an empty inventory;
the vision model does the reading. Includes a light enhancement for photos of drawings."""
from __future__ import annotations

import io
from pathlib import Path
from typing import List

from PIL import Image, ImageOps

from app.extract.inventory import SheetInventory


def read_image(path: Path) -> List[SheetInventory]:
    with Image.open(path) as im:
        frames = getattr(im, "n_frames", 1)
        out = []
        for i in range(frames):
            try:
                im.seek(i)
            except Exception:
                pass
            inv = SheetInventory(source=path.name, page_no=i + 1, layout=f"Image {i + 1}",
                                 width=float(im.width), height=float(im.height), units_hint="unknown")
            inv.notes.append("raster drawing: no machine-readable text, vision model required")
            inv.entity_counts = {"pixels": im.width * im.height}
            out.append(inv)
        return out


def render_image_png(path: Path, page_no: int = 1, max_px: int = 3000, enhance: bool = True) -> bytes:
    with Image.open(path) as im:
        try:
            im.seek(page_no - 1)
        except Exception:
            pass
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        if enhance and im.mode == "RGB":
            # photos of prints: mild autocontrast keeps thin lines legible
            im = ImageOps.autocontrast(im, cutoff=1)
        if max(im.size) > max_px:
            ratio = max_px / max(im.size)
            im = im.resize((max(1, int(im.width * ratio)), max(1, int(im.height * ratio))), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
