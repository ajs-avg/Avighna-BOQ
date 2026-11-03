"""Find the parts of a sheet that must NOT be read: blocks crossed out with a big X,
and blocks carrying warning words such as "NOT TO REFER" or "SUPERSEDED"."""
from __future__ import annotations

import math
import re
from typing import List, Tuple

WARNING_RX = re.compile(
    r"\bNOT\b.*\b(REFER|USE|USED|APPLICABLE|VALID|FOR CONSTRUCTION)\b|SUPERSED|CANCEL|\bVOID\b|OBSOLETE|DO NOT USE",
    re.I,
)

Box = Tuple[float, float, float, float]


def find_excluded(doc) -> Tuple[List[Tuple[str, float, float]], List[Box]]:
    """Returns (warning_words, crossed_out_boxes).

    warning_words: (text, x, y) for every warning text found.
    crossed_out_boxes: (x0, y0, x1, y1) for every box struck through by two
    opposite diagonals (an X over an old table or detail).
    """
    msp = doc.modelspace()
    words: List[Tuple[str, float, float]] = []
    for e in msp.query("TEXT MTEXT"):
        try:
            t = e.dxf.text if e.dxftype() == "TEXT" else e.plain_text()
        except Exception:  # noqa: BLE001
            continue
        if WARNING_RX.search(t or ""):
            p = e.dxf.insert
            words.append((t.strip(), p.x, p.y))

    # Diagonal lines (neither horizontal nor vertical) are X candidates.
    lines: List[Tuple[float, float, float, float, float]] = []
    for e in msp.query("LINE"):
        a, b = e.dxf.start, e.dxf.end
        L = math.hypot(b.x - a.x, b.y - a.y)
        if L > 0 and abs(b.x - a.x) > 0.2 * L and abs(b.y - a.y) > 0.2 * L:
            lines.append((a.x, a.y, b.x, b.y, L))
    for e in msp.query("LWPOLYLINE"):
        pts = list(e.get_points("xy"))
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            L = math.hypot(x2 - x1, y2 - y1)
            if L > 0 and abs(x2 - x1) > 0.2 * L and abs(y2 - y1) > 0.2 * L:
                lines.append((x1, y1, x2, y2, L))
    lines.sort(key=lambda l: -l[4])
    lines = lines[:400]

    boxes: List[Box] = []
    for i, a in enumerate(lines):
        ax0, ax1 = sorted((a[0], a[2]))
        ay0, ay1 = sorted((a[1], a[3]))
        for b in lines[i + 1:]:
            bx0, bx1 = sorted((b[0], b[2]))
            by0, by1 = sorted((b[1], b[3]))
            tol = 0.02 * max(ax1 - ax0, ay1 - ay0)
            if all(abs(u - v) < tol for u, v in [(ax0, bx0), (ax1, bx1), (ay0, by0), (ay1, by1)]):
                sa = (a[3] - a[1]) * (a[2] - a[0])
                sb = (b[3] - b[1]) * (b[2] - b[0])
                if sa * sb < 0:   # opposite slopes: the two diagonals of one box
                    boxes.append((ax0, ay0, ax1, ay1))
    out: List[Box] = []
    for b in boxes:
        # Only big boxes count: an old table or detail block. Small X marks (lift
        # shafts, stair crosses, column symbols) are drawing content, not exclusions.
        if (b[2] - b[0]) < 5000 or (b[3] - b[1]) < 5000:
            continue
        if not any(all(abs(u - v) < 1e-3 * max(1.0, abs(v)) for u, v in zip(b, o)) for o in out):
            out.append(b)
    return words, out


def in_any_box(x: float, y: float, boxes: List[Box]) -> bool:
    return any(b[0] <= x <= b[2] and b[1] <= y <= b[3] for b in boxes)
