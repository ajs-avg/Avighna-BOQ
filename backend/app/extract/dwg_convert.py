"""DWG -> DXF conversion.

Primary: ODA File Converter (free, from opendesign.com; installed in the Docker image).
Fallback: LibreDWG `dwg2dxf` (apt package libredwg-tools).
Both are invoked as subprocesses; nothing here depends on their Python bindings.
"""
from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional

from app.config import get_settings

log = logging.getLogger(__name__)


class ConversionError(RuntimeError):
    pass


def converter_status() -> Dict[str, bool]:
    s = get_settings()
    return {
        "oda": shutil.which(s.oda_converter_bin) is not None,
        "libredwg": bool(_libredwg_bins()),
    }


def _run(cmd: list, timeout: int) -> subprocess.CompletedProcess:
    log.info("running: %s", " ".join(str(c) for c in cmd))
    # LibreDWG echoes raw strings from the DWG (layout names, texts) that are often not UTF-8;
    # never let decoding its chatter crash the conversion.
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _oda_convert(src: Path, out_dir: Path, version: str = "ACAD2018") -> Optional[Path]:
    s = get_settings()
    exe = shutil.which(s.oda_converter_bin)
    if not exe:
        return None
    in_dir = Path(tempfile.mkdtemp(prefix="oda_in_"))
    tmp_src = in_dir / src.name
    shutil.copy2(src, tmp_src)
    out_dir.mkdir(parents=True, exist_ok=True)
    # ODAFileConverter <in_dir> <out_dir> <version> <type> <recurse 0/1> <audit 0/1> [filter]
    cmd = [exe, str(in_dir), str(out_dir), version, "DXF", "0", "1", src.name]
    if platform.system() == "Linux" and shutil.which("xvfb-run") and not os.environ.get("DISPLAY"):
        cmd = ["xvfb-run", "-a"] + cmd
    try:
        proc = _run(cmd, s.conversion_timeout_s)
    except subprocess.TimeoutExpired as exc:
        raise ConversionError(f"ODA File Converter timed out after {s.conversion_timeout_s}s") from exc
    finally:
        shutil.rmtree(in_dir, ignore_errors=True)
    dxf = out_dir / (src.stem + ".dxf")
    if dxf.exists() and dxf.stat().st_size > 0:
        return dxf
    log.warning("ODA conversion produced no output (rc=%s): %s %s", proc.returncode, proc.stdout[-500:], proc.stderr[-500:])
    return None


def _libredwg_bins() -> list:
    s = get_settings()
    out = []
    for cand in s.libredwg_candidates:
        exe = shutil.which(cand) if os.sep not in cand else (cand if os.path.exists(cand) else None)
        if exe and exe not in out:
            out.append(exe)
    return out


def _libredwg_convert(src: Path, out_dir: Path) -> Optional[Path]:
    """Try every available dwg2dxf build (newest first); different versions fail on different files."""
    s = get_settings()
    out_dir.mkdir(parents=True, exist_ok=True)
    dxf = out_dir / (src.stem + ".dxf")
    for exe in _libredwg_bins():
        if dxf.exists():
            dxf.unlink()
        try:
            proc = _run([exe, "-y", "-o", str(dxf), str(src)], s.conversion_timeout_s)
        except subprocess.TimeoutExpired:
            log.warning("%s timed out on %s", exe, src.name)
            continue
        if dxf.exists() and dxf.stat().st_size > 1000:
            if sanitize_dxf(dxf):
                log.info("converted %s with %s", src.name, exe)
                return dxf
            log.warning("%s produced an unreadable DXF for %s; trying next converter", exe, src.name)
            continue
        log.warning("%s failed on %s (rc=%s): %s", exe, src.name, proc.returncode, (proc.stderr or proc.stdout)[-300:])
    return None


def convert_dwg_to_dxf(src: Path, out_dir: Path) -> Path:
    """Convert with the best available tool; raise ConversionError when none works."""
    errors = []
    for name, fn in (("ODA File Converter", _oda_convert), ("LibreDWG dwg2dxf", _libredwg_convert)):
        try:
            result = fn(src, out_dir)
        except ConversionError as exc:
            errors.append(f"{name}: {exc}")
            continue
        if result:
            log.info("converted %s with %s", src.name, name)
            return result
        errors.append(f"{name}: not available or produced no output")
    status = converter_status()
    raise ConversionError(
        "DWG conversion failed. " + "; ".join(errors)
        + f". Converters present: ODA={status['oda']}, libredwg={status['libredwg']}. "
        "Upload a DXF or PDF export of the drawing instead."
    )

# ----------------------------------------------------------------------------- DXF sanitising
_DROP_OBJECT_TYPES = ("SORTENTSTABLE",)


def _strip_dxf_objects(text: str, types=_DROP_OBJECT_TYPES) -> str:
    """Drop whole DXF objects of the given types. DXF is a stream of (group code, value) line
    pairs; an object starts at a pair whose code is 0. Pairs are walked two lines at a time so a
    *value* that happens to be "0" (e.g. an owner handle) is never mistaken for a group code.
    LibreDWG 0.13 writes SORTENTSTABLE records that ezdxf rejects; they only affect draw order."""
    lines = text.split("\n")
    out, skip, n, i = [], False, len(lines), 0
    while i + 1 < n:
        code, value = lines[i], lines[i + 1]
        if code.strip() == "0":
            skip = value.strip() in types
        if not skip:
            out.append(code)
            out.append(value)
        i += 2
    if i < n:
        out.append(lines[i])
    return "\n".join(out)


def load_dxf_lenient(path: Path):
    """ezdxf document for a converted DXF: plain read, then recover mode (tolerates the loose
    structure LibreDWG writes: dangling layout keys, bad sort tables, odd MTEXT versions)."""
    import ezdxf
    from ezdxf import recover
    try:
        return ezdxf.readfile(str(path))
    except Exception as exc:  # DXFStructureError, KeyError on layouts, ...
        log.info("plain DXF load failed for %s (%s); using recover mode", path.name, str(exc)[:80])
    doc, auditor = recover.readfile(str(path))
    if auditor.has_errors:
        log.info("DXF %s recovered with %d errors / %d fixes", path.name, len(auditor.errors), len(auditor.fixes))
    return doc


def sanitize_dxf(path: Path) -> bool:
    """Make a converted DXF loadable; returns True if ezdxf can load it (plain or recover mode)."""
    import ezdxf
    try:
        ezdxf.readfile(str(path))
        return True
    except Exception as exc:
        log.info("sanitising %s (%s)", path.name, str(exc)[:80])
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        path.write_text(_strip_dxf_objects(text), encoding="utf-8")
        load_dxf_lenient(path)
        return True
    except Exception as exc:
        log.warning("DXF still unreadable after sanitising %s: %s", path.name, str(exc)[:120])
        return False
