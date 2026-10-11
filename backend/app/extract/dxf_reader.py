"""Read a DXF (converted DWG) into SheetInventory objects, one per layout, and render previews."""
from __future__ import annotations

import io
import logging
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import ezdxf
from ezdxf.document import Drawing

from app.extract.inventory import SheetInventory, TextItem, guess_units

log = logging.getLogger(__name__)

INSUNITS = {0: "unknown", 1: "in", 2: "ft", 4: "mm", 5: "cm", 6: "m", 14: "dm"}


_DOC_CACHE: Dict[str, Drawing] = {}


def load_dxf(path: Path) -> Drawing:
    """Load (and cache) a DXF; run the auditor so dangling block references left behind by
    DWG converters (e.g. anonymous "*U" blocks) cannot break bbox/render later."""
    key = f"{path}:{path.stat().st_mtime_ns}"
    if key in _DOC_CACHE:
        return _DOC_CACHE[key]
    from app.extract.dwg_convert import load_dxf_lenient, sanitize_dxf
    try:
        doc = load_dxf_lenient(path)
    except Exception:
        if not sanitize_dxf(path):
            raise
        doc = load_dxf_lenient(path)
    # NOTE: no doc.audit() here - the auditor deletes INSERTs whose block definition was lost by
    # the DWG converter, and with them their ATTRIB texts (finish tags, view titles). Rendering
    # does its own cleanup in a subprocess (render_cli.py); bbox handles dangling inserts below.
    if len(_DOC_CACHE) > 8:
        _DOC_CACHE.clear()
    _DOC_CACHE[key] = doc
    return doc


def _drop_dangling_inserts(doc: Drawing) -> None:
    """Remove INSERTs whose block definition is missing (left by partial DWG conversion)."""
    removed = 0
    layouts = [doc.modelspace()] + [doc.layout(n) for n in doc.layout_names_in_taborder() if n.lower() != "model"]
    for lay in layouts:
        for e in list(lay.query("INSERT")):
            if e.dxf.name not in doc.blocks:
                lay.delete_entity(e)
                removed += 1
    for blk in doc.blocks:
        for e in list(blk.query("INSERT")):
            if e.dxf.name not in doc.blocks:
                blk.delete_entity(e)
                removed += 1
    if removed:
        log.info("dropped %d INSERT(s) with missing block definitions", removed)


def paperspace_hints(doc: Drawing, max_items: int = 200) -> List[str]:
    """Title-block style strings from paperspace layouts (drawing no, title, scale...)."""
    out: List[str] = []
    seen = set()
    for name in doc.layout_names_in_taborder():
        if name.lower() == "model":
            continue
        lay = doc.layout(name)
        for e in lay:
            t = e.dxftype()
            texts: List[str] = []
            try:
                if t == "TEXT":
                    texts = [e.dxf.text]
                elif t == "MTEXT":
                    texts = e.plain_text().split("\n")
                elif t == "INSERT":
                    texts = [a.dxf.text for a in e.attribs if a.dxf.text]
                    try:
                        for sub in e.virtual_entities():
                            if sub.dxftype() == "TEXT":
                                texts.append(sub.dxf.text)
                            elif sub.dxftype() == "MTEXT":
                                texts.extend(sub.plain_text().split("\n"))
                    except Exception:
                        pass
            except Exception:
                continue
            for x in texts:
                x = " ".join((x or "").split())
                if x and x not in seen:
                    seen.add(x)
                    out.append(x)
                    if len(out) >= max_items:
                        return out
    return out


def _text_bbox(entity, text: str, height: float) -> Tuple[float, float, float, float]:
    try:
        from ezdxf import bbox as _bbox
        box = _bbox.extents([entity], fast=True)
        if box.has_data:
            return box.extmin.x, box.extmin.y, box.size.x, box.size.y
    except Exception:
        pass
    ins = entity.dxf.insert if entity.dxf.hasattr("insert") else None
    x, y = (ins.x, ins.y) if ins else (0.0, 0.0)
    w = max(len(text), 1) * height * 0.7
    return x, y, w, height


def _collect_texts(layout, inv: SheetInventory, transform=None) -> None:
    for e in layout:
        kind = e.dxftype()
        try:
            if kind == "TEXT":
                text = e.dxf.text
                h = float(e.dxf.height or 2.5)
                x, y, w, hh = _text_bbox(e, text, h)
                inv.add(TextItem(text, x, y, w, hh, e.dxf.layer, "text", float(e.dxf.rotation or 0)))
            elif kind == "MTEXT":
                text = e.plain_text()
                h = float(e.dxf.char_height or 2.5)
                x, y, w, hh = _text_bbox(e, text, h)
                for line in text.split("\n"):
                    inv.add(TextItem(line, x, y, w, h, e.dxf.layer, "mtext", float(e.dxf.rotation or 0)))
                    y -= h * 1.4
            elif kind == "DIMENSION":
                override = (e.dxf.text or "").strip()
                value: Optional[float] = None
                try:
                    value = float(e.get_measurement())
                except Exception:
                    pass
                if override in ("", "<>"):
                    label = f"{value:.0f}" if value is not None else ""
                else:
                    label = override.replace("<>", f"{value:.0f}" if value is not None else "")
                if label:
                    pt = e.dxf.text_midpoint if e.dxf.hasattr("text_midpoint") else e.dxf.defpoint
                    inv.add(TextItem(label, pt.x, pt.y, 0, 2.5, e.dxf.layer, "dimension"))
            elif kind == "INSERT":
                inv.block_names.append(e.dxf.name)
                for att in e.attribs:
                    if att.dxf.text:
                        h = float(att.dxf.height or 2.5)
                        x, y, w, hh = _text_bbox(att, att.dxf.text, h)
                        inv.add(TextItem(att.dxf.text, x, y, w, hh, att.dxf.layer, "attrib"))
                # explode nested block text (schedules are often blocks)
                try:
                    for sub in e.virtual_entities():
                        st = sub.dxftype()
                        if st == "TEXT" and sub.dxf.text:
                            h = float(sub.dxf.height or 2.5)
                            x, y, w, hh = _text_bbox(sub, sub.dxf.text, h)
                            inv.add(TextItem(sub.dxf.text, x, y, w, hh, sub.dxf.layer, "block"))
                        elif st == "MTEXT":
                            text = sub.plain_text()
                            h = float(sub.dxf.char_height or 2.5)
                            x, y, w, hh = _text_bbox(sub, text, h)
                            for line in text.split("\n"):
                                inv.add(TextItem(line, x, y, w, h, sub.dxf.layer, "block"))
                                y -= h * 1.4
                except Exception:
                    pass
            elif kind == "ACAD_TABLE":
                try:
                    for sub in e.virtual_entities():
                        if sub.dxftype() in ("TEXT", "MTEXT"):
                            text = sub.dxf.text if sub.dxftype() == "TEXT" else sub.plain_text()
                            h = float(getattr(sub.dxf, "height", None) or getattr(sub.dxf, "char_height", None) or 2.5)
                            x, y, w, hh = _text_bbox(sub, text, h)
                            inv.add(TextItem(text, x, y, w, hh, sub.dxf.layer, "text"))
                except Exception:
                    pass
        except Exception as exc:  # never let one bad entity kill the sheet
            inv.notes.append(f"skipped {kind}: {exc}")


def read_dxf(path: Path, include_paperspace: bool = True) -> List[SheetInventory]:
    doc = load_dxf(path)
    units = INSUNITS.get(int(doc.header.get("$INSUNITS", 0)), "unknown")
    layers = [l.dxf.name for l in doc.layers]
    inventories: List[SheetInventory] = []

    layouts = [doc.modelspace()]
    if include_paperspace:
        for name in doc.layout_names_in_taborder():
            if name.lower() != "model":
                layouts.append(doc.layout(name))

    for lay in layouts:
        name = "Model" if lay.is_modelspace else lay.name
        inv = SheetInventory(source=path.name, page_no=len(inventories) + 1, layout=name, units_hint=units)
        inv.layers = layers
        counts = Counter(e.dxftype() for e in lay)
        inv.entity_counts = dict(counts)
        _collect_texts(lay, inv)
        if lay.is_modelspace or inv.texts:
            try:
                from ezdxf import bbox as _bbox
                safe = [e for e in lay if not (e.dxftype() == "INSERT" and e.dxf.name not in doc.blocks)]
                box = _bbox.extents(safe, fast=True)
                if box.has_data:
                    inv.width, inv.height = float(box.size.x), float(box.size.y)
                    # shift texts so origin = extmin (keeps normalised coords sane)
                    ox, oy = float(box.extmin.x), float(box.extmin.y)
                    for t in inv.texts:
                        t.x -= ox
                        t.y -= oy
            except Exception as exc:
                inv.notes.append(f"bbox failed: {exc}")
            if inv.units_hint == "unknown":
                inv.units_hint = guess_units(inv)
            inventories.append(inv)
    # paperspace viewports show model content; if paperspace has only title text, keep model as primary
    return inventories or [SheetInventory(source=path.name, units_hint=units, layers=layers)]


def render_layout_png(path: Path, layout_name: str = "Model", max_px: int = 3000, dpi: int = 110,
                      timeout_s: int = 180) -> bytes:
    """Render a layout to PNG in an isolated subprocess (see render_cli.py); raises RuntimeError on failure."""
    import os
    import subprocess
    import sys
    import tempfile

    out = Path(tempfile.mkdtemp(prefix="dxfpng_")) / "layout.png"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2]) + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("PYTHONWARNINGS", "ignore")
    cmd = [sys.executable, "-m", "app.extract.render_cli", str(path), layout_name, str(out), str(max_px), str(dpi)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout_s, env=env)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"render timed out after {timeout_s}s")
    if proc.returncode != 0 or not out.exists():
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        raise RuntimeError(f"render failed (rc={proc.returncode}): {' | '.join(tail)[:300]}")
    data = out.read_bytes()
    try:
        out.unlink()
        out.parent.rmdir()
    except OSError:
        pass
    return data


def _limit_png(png: bytes, max_px: int) -> bytes:
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(png))
        if max(im.size) <= max_px:
            return png
        ratio = max_px / max(im.size)
        im = im.convert("RGB").resize((int(im.width * ratio), int(im.height * ratio)))
        out = io.BytesIO()
        im.save(out, format="PNG", optimize=True)
        return out.getvalue()
    except Exception:
        return png
