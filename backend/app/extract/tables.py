"""Rebuild schedule tables (beam / column schedules) from loose text items.

CAD schedules are just text placed in a grid of lines; we cluster the text by
y (rows) and by x (columns) and emit a markdown table that Gemini reads very
reliably. Works on DXF and vector-PDF inventories alike.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence

from app.extract.inventory import SheetInventory, TextItem


@dataclass
class TableBlock:
    rows: List[List[str]]
    x0: float
    y0: float
    x1: float
    y1: float
    n_cols: int = 0

    def to_markdown(self, max_rows: int = 120) -> str:
        if not self.rows:
            return ""
        width = max(len(r) for r in self.rows)
        lines = []
        for i, r in enumerate(self.rows[:max_rows]):
            cells = [c.replace("|", "/") for c in r] + [""] * (width - len(r))
            lines.append("| " + " | ".join(cells) + " |")
            if i == 0:
                lines.append("|" + "---|" * width)
        if len(self.rows) > max_rows:
            lines.append(f"| ... {len(self.rows) - max_rows} more rows |")
        return "\n".join(lines)


@dataclass
class _Row:
    y: float
    items: List[TextItem] = field(default_factory=list)


def _cluster_rows(items: Sequence[TextItem], tol: float) -> List[_Row]:
    rows: List[_Row] = []
    for it in sorted(items, key=lambda t: -t.cy):
        if rows and abs(rows[-1].y - it.cy) <= tol:
            rows[-1].items.append(it)
            rows[-1].y = (rows[-1].y * (len(rows[-1].items) - 1) + it.cy) / len(rows[-1].items)
        else:
            rows.append(_Row(y=it.cy, items=[it]))
    for r in rows:
        r.items.sort(key=lambda t: t.x)
    return rows


def _column_edges(rows: Sequence[_Row], tol: float) -> List[float]:
    xs = sorted(it.x for r in rows for it in r.items)
    if not xs:
        return []
    edges: List[float] = []
    cluster = [xs[0]]
    for x in xs[1:]:
        if x - cluster[-1] <= tol:
            cluster.append(x)
        else:
            edges.append(sum(cluster) / len(cluster))
            cluster = [x]
    edges.append(sum(cluster) / len(cluster))
    return edges


def reconstruct_tables(inv: SheetInventory, min_rows: int = 3, min_cols: int = 2,
                       gap_factor: float = 2.5) -> List[TableBlock]:
    """Find rectangular text grids. Strategy:
    1. cluster all texts into rows by y
    2. split the sheet into vertical bands where consecutive rows are close
    3. inside each band, derive column edges from x positions and fill cells
    """
    if not inv.texts:
        return []
    tol = inv.row_tolerance()
    rows = _cluster_rows(inv.texts, tol)
    if not rows:
        return []
    # typical row pitch
    pitches = [abs(rows[i].y - rows[i + 1].y) for i in range(len(rows) - 1)]
    pitches = sorted(p for p in pitches if p > 0)
    pitch = pitches[len(pitches) // 2] if pitches else tol * 3
    bands: List[List[_Row]] = [[rows[0]]]
    for r in rows[1:]:
        if abs(bands[-1][-1].y - r.y) <= pitch * gap_factor:
            bands[-1].append(r)
        else:
            bands.append([r])

    tables: List[TableBlock] = []
    for band in bands:
        multi = [r for r in band if len(r.items) >= min_cols]
        if len(multi) < min_rows:
            continue
        # split band horizontally into groups of overlapping x-extents (two tables side by side)
        edges = _column_edges(multi, tol * 2.5)
        if len(edges) < min_cols:
            continue
        grid: List[List[str]] = []
        for r in multi:
            cells = [""] * len(edges)
            for it in r.items:
                # nearest edge to the left of the item start
                idx = max(i for i, e in enumerate(edges) if e <= it.x + tol * 2.5) if any(e <= it.x + tol * 2.5 for e in edges) else 0
                cells[idx] = (cells[idx] + " " + it.text).strip()
            grid.append(cells)
        # drop empty columns
        keep = [i for i in range(len(edges)) if any(row[i] for row in grid)]
        grid = [[row[i] for i in keep] for row in grid]
        xs = [it.x for r in multi for it in r.items]
        ys = [it.y for r in multi for it in r.items]
        tables.append(TableBlock(rows=grid, x0=min(xs), y0=min(ys),
                                 x1=max(it.x + it.w for r in multi for it in r.items), y1=max(ys),
                                 n_cols=len(keep)))
    return tables


def tables_to_prompt(tables: Sequence[TableBlock], max_tables: int = 12) -> str:
    if not tables:
        return "(no tabular schedules detected)"
    parts = []
    for i, t in enumerate(tables[:max_tables], 1):
        parts.append(f"### Table {i} ({len(t.rows)} rows x {t.n_cols} cols)\n{t.to_markdown()}")
    return "\n\n".join(parts)
