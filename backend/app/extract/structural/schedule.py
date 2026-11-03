"""Read the beam schedule and slab schedule printed on the sheet.

The schedule is the drawing's own table of every beam (name, width B, depth D,
bars, remarks). It lives outside the plan region. Layout differs per consultant,
so the parse is positional, not keyword-based: find the vertical strip of member
names, band the rows between consecutive names, then read each row's numbers from
left to right.

The diameter symbol is stored as an odd character in DXF text (\\x7f or %%C);
both are mapped to "T" (T8, T20...).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from app.extract.structural.entities import TextItem
from app.extract.structural.exclusions import Box, in_any_box

BEAM_NAME_RX = re.compile(r"^(B\d+[A-Z]?|BKT[\w-]*|HB)(,(B\d+[A-Z]?|BKT[\w-]*|HB))*,?$")
SLAB_NAME_RX = re.compile(r"^S\d+[A-Z]?$")
REMARK_KINDS = (("CANTILEVER", "cantilever"), ("INVERT", "inverted"), ("SUNK", "sunken"))


def _norm(t: str) -> str:
    return t.replace("\x7f", "T").replace("%%C", "T").replace("%%c", "T").replace(" ", "").upper()


@dataclass
class ScheduleRow:
    names: List[str]
    B: Optional[int] = None            # width, mm
    D: Optional[int] = None            # depth, mm (of "750/500" the first value)
    D_raw: str = ""
    kind: str = ""                     # cantilever | inverted | sunken | ""
    cells: List[str] = field(default_factory=list)   # the row's raw text, left to right


@dataclass
class BeamSchedule:
    rows: List[ScheduleRow] = field(default_factory=list)
    by_name: Dict[str, ScheduleRow] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def width(self, name: str) -> Optional[int]:
        r = self.by_name.get(name)
        return r.B if r else None


def _name_column(cands: Sequence[TextItem], bin_w: float = 1250.0) -> List[TextItem]:
    """The schedule's name column is a dense vertical strip: many names sharing
    (nearly) one x. Bin the x positions and take the densest bin and its two
    neighbours — scattered plan labels never concentrate like that."""
    if not cands:
        return []
    bins: Dict[int, List[TextItem]] = {}
    for t in cands:
        bins.setdefault(int(t.cx // bin_w), []).append(t)
    k = max(bins, key=lambda k: len(bins[k]))
    return bins.get(k - 1, []) + bins[k] + bins.get(k + 1, [])


def _parse_rows(names: List[TextItem], texts: Sequence[TextItem],
                first_num_range: Tuple[int, int], second_num_range: Tuple[int, int],
                row_up: float = 700.0, row_down: float = 900.0, reach: float = 45000.0,
                ) -> List[ScheduleRow]:
    names = sorted(names, key=lambda t: -t.cy)
    x_left = min(t.cx for t in names)
    rows: List[ScheduleRow] = []
    for i, n in enumerate(names):
        top = (names[i - 1].cy + n.cy) / 2 if i else n.cy + row_up
        bot = (n.cy + names[i + 1].cy) / 2 if i + 1 < len(names) else n.cy - row_down
        cells = sorted((t for t in texts
                        if bot < t.cy <= top and x_left + 300 < t.cx < x_left + reach),
                       key=lambda t: t.cx)
        row = ScheduleRow(names=[v for v in _norm(n.text).rstrip(",").split(",") if v],
                          cells=[_norm(t.text) for t in cells])
        for raw in row.cells:
            if row.B is None:
                m = re.match(r"^(\d{3})(\+\d+)?$", raw)
                if m and first_num_range[0] <= int(m.group(1)) <= first_num_range[1]:
                    row.B = int(m.group(1))
                    continue
            elif row.D is None or (row.D == row.B and not row.D_raw.count("/")):
                m = re.match(r"^(\d{3,4})(/\d{3,4})?(\+\d+)?$", raw)
                if m and second_num_range[0] <= int(m.group(1)) <= second_num_range[1]:
                    # a bare repeat of B is usually another column of the table;
                    # prefer the next number as the depth
                    row.D = int(m.group(1))
                    row.D_raw = raw
                    continue
            for word, kind in REMARK_KINDS:
                if word in raw:
                    row.kind = kind
        rows.append(row)
    return rows


def parse_beam_schedule(texts: Sequence[TextItem], plan_region: Optional[List[float]],
                        excluded: Sequence[Box] = ()) -> BeamSchedule:
    def outside(t: TextItem) -> bool:
        if in_any_box(t.cx, t.cy, list(excluded)):
            return False
        if plan_region is None:
            return True
        return not (plan_region[0] <= t.cx <= plan_region[2] and plan_region[1] <= t.cy <= plan_region[3])

    pool = [t for t in texts if outside(t)]
    cands = [t for t in pool if BEAM_NAME_RX.match(_norm(t.text).rstrip(","))]
    sched = BeamSchedule()
    col = _name_column(cands)
    if len(col) < 3:
        sched.notes.append("no beam schedule found on the sheet")
        return sched
    strip = [t for t in pool if abs(t.cx - sorted(c.cx for c in col)[len(col) // 2]) < 60000]
    sched.rows = _parse_rows(col, strip, first_num_range=(100, 650), second_num_range=(200, 2500))
    for r in sched.rows:
        if r.B is None or r.D is None:
            continue
        for nm in r.names:
            sched.by_name[nm] = r
    sched.notes.append(f"beam schedule: {len(sched.rows)} rows, {len(sched.by_name)} named beams")
    return sched


def parse_slab_schedule(texts: Sequence[TextItem], plan_region: Optional[List[float]],
                        excluded: Sequence[Box] = ()) -> Dict[str, int]:
    """Slab tag -> thickness in mm, from the slab schedule table."""
    def outside(t: TextItem) -> bool:
        if in_any_box(t.cx, t.cy, list(excluded)):
            return False
        if plan_region is None:
            return True
        return not (plan_region[0] <= t.cx <= plan_region[2] and plan_region[1] <= t.cy <= plan_region[3])

    pool = [t for t in texts if outside(t)]
    cands = [t for t in pool if SLAB_NAME_RX.match(_norm(t.text))]
    col = _name_column(cands)
    if len(col) < 3:
        return {}
    strip = [t for t in pool if abs(t.cx - sorted(c.cx for c in col)[len(col) // 2]) < 60000]
    rows = _parse_rows(col, strip, first_num_range=(75, 400), second_num_range=(75, 400),
                       row_up=500.0, row_down=700.0, reach=30000.0)
    return {nm: r.B for r in rows if r.B is not None for nm in r.names}
