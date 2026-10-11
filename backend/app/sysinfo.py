"""Container / machine memory facts used to keep big CAD files from crashing a small server."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def memory_limit_mb() -> Optional[float]:
    """Memory available to this process: MEMORY_LIMIT_MB env, else cgroup limit (Render/Docker),
    else physical RAM. None when unknown."""
    env = os.getenv("MEMORY_LIMIT_MB")
    if env:
        try:
            return float(env)
        except ValueError:
            pass
    for p in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            raw = Path(p).read_text().strip()
            if raw and raw != "max":
                val = int(raw)
                if 0 < val < 1 << 50:
                    return round(val / 1e6, 0)
        except (OSError, ValueError):
            continue
    if os.getenv("RENDER"):   # Render containers do not expose a cgroup limit; the free/starter plans have 512 MB
        return 512.0
    try:
        pages, size = os.sysconf("SC_PHYS_PAGES"), os.sysconf("SC_PAGE_SIZE")
        if pages > 0 and size > 0:
            return round(pages * size / 1e6, 0)
    except (ValueError, OSError, AttributeError):
        pass
    return None


# Measured: a 20 MB DXF needs ~400 MB to load in ezdxf and ~480 MB to render -> ~25x its size.
DXF_MEMORY_FACTOR = 25.0
BASELINE_MB = 180.0  # API process with PyMuPDF/matplotlib imported


def max_dxf_mb() -> Optional[float]:
    """Largest DXF this server can safely parse (None = no limit known)."""
    limit = memory_limit_mb()
    if limit is None:
        return None
    return round(max((limit - BASELINE_MB) / DXF_MEMORY_FACTOR, 2.0), 1)


def dxf_too_large(size_bytes: int) -> Optional[str]:
    cap = max_dxf_mb()
    mb = size_bytes / 1e6
    if cap is not None and mb > cap:
        lim = memory_limit_mb()
        return (f"DXF is {mb:.1f} MB but this server ({lim:.0f} MB RAM) can safely parse about {cap:.0f} MB. "
                f"Upload the PDF plot instead, split the drawing, or run the API on a bigger instance.")
    return None
