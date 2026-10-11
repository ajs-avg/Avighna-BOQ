"""Detect the real format of an uploaded file from its bytes (never trust the extension alone)."""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Tuple

Format = Literal["dwg", "dxf", "pdf", "image", "unknown"]

DWG_VERSIONS = {
    b"AC1006": "R10", b"AC1009": "R11/R12", b"AC1012": "R13", b"AC1014": "R14",
    b"AC1015": "AutoCAD 2000", b"AC1018": "AutoCAD 2004", b"AC1021": "AutoCAD 2007",
    b"AC1024": "AutoCAD 2010", b"AC1027": "AutoCAD 2013", b"AC1032": "AutoCAD 2018+",
}

IMAGE_MAGIC = {
    b"\x89PNG": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF8": "image/gif",
    b"II*\x00": "image/tiff",
    b"MM\x00*": "image/tiff",
    b"BM": "image/bmp",
    b"RIFF": "image/webp",
}


def detect_format(path: Path) -> Tuple[Format, str, str]:
    """Return (format, mime, detail)."""
    with open(path, "rb") as fh:
        head = fh.read(4096)
    if head[:2] == b"AC" and head[:6] in DWG_VERSIONS:
        return "dwg", "application/acad", DWG_VERSIONS[head[:6]]
    if head[:5] == b"%PDF-":
        return "pdf", "application/pdf", head[:8].decode("ascii", "replace")
    for magic, mime in IMAGE_MAGIC.items():
        if head.startswith(magic):
            if magic == b"RIFF" and head[8:12] != b"WEBP":
                continue
            return "image", mime, mime.split("/")[1]
    text = head.decode("ascii", "replace")
    if "SECTION" in text and ("HEADER" in text or "ENTITIES" in text or "$ACADVER" in text):
        return "dxf", "application/dxf", "ascii"
    if head[:22] == b"AutoCAD Binary DXF\r\n\x1a\x00":
        return "dxf", "application/dxf", "binary"
    ext = path.suffix.lower()
    if ext == ".dxf":
        return "dxf", "application/dxf", "by-extension"
    if ext == ".dwg":
        return "dwg", "application/acad", "by-extension"
    return "unknown", "application/octet-stream", ""
