"""Column / lift-wall BBS — reproduces the '13th To 14th Column' sheet logic.

  Vertical bars : cut = H + Ld x d (lap at floor level)
  Main ring     : cut = 2(a-2c) + 2(b-2c) + 2 x 10d - 5 x 0.6d ; n = (ROUND((H-2c)/s) + 1) x per_layer
  Inner tie     : cut = leg + 2 x 10d - 2 x 0.6d               ; n = (ROUND((H-2c)/s) + 1) x per_layer
"""
from __future__ import annotations

from typing import List, Tuple

from app.engine.common import RowBuilder, bars_label, fmt, lap_length, xround
from app.models.schemas import BarRow, ColumnSpec, Standards


def compute_column(spec: ColumnSpec, std: Standards) -> Tuple[List[BarRow], List[str]]:
    rb = RowBuilder(std, spec.nos)
    c = std.cover_column_mm / 1000.0
    H = spec.height_m
    a_in = spec.length_m - 2 * c
    b_in = spec.width_m - 2 * c

    for g in spec.vertical_bars:
        if g.count <= 0:
            continue
        lap = lap_length(std, g.dia_mm) if spec.lap_at_floor else 0.0
        rb.add(f"Vertical Bar {g.count}-T{g.dia_mm}", g.dia_mm, g.count,
               d=round(H, 4), g=round(lap, 4),
               formula=f"H {fmt(H)} + lap Ld x d {fmt(lap)}")

    for t in spec.ties:
        if t.spacing_mm <= 0:
            rb.warnings.append("Tie spacing missing; row skipped")
            continue
        s = t.spacing_mm / 1000.0
        n_layers = xround((H - 2 * c) / s) + 1
        n = n_layers * max(t.per_layer, 1)
        hooks = t.dia_mm * std.hook_length_d * 2 / 1000.0
        if t.kind == "main_ring":
            rb.add(f"Main Ring T{t.dia_mm} @{int(t.spacing_mm)} c/c", t.dia_mm, n,
                   a=round(a_in, 4), b=round(a_in, 4), c=round(b_in, 4), d=round(b_in, 4),
                   e=round(hooks, 4), bend_corners=std.stirrup_corners,
                   spacing_mm=t.spacing_mm, span_m=round(H - 2 * c, 4), shape="ring",
                   formula=f"n = (ROUND(({fmt(H)} - 2c)/{fmt(s)}) + 1) x {t.per_layer} = {int(n)}; "
                           f"cut = 2({fmt(a_in)}) + 2({fmt(b_in)}) + hooks {fmt(hooks)} - {std.stirrup_corners}x0.6d")
        else:
            leg = t.leg_length_m if t.leg_length_m else (b_in if t.kind == "inner_tie" else a_in)
            rb.add(f"{'Inner Tie' if t.kind == 'inner_tie' else 'Cross Tie'} T{t.dia_mm} @{int(t.spacing_mm)} c/c",
                   t.dia_mm, n,
                   c=round(leg, 4), e=round(hooks, 4), bend_corners=2,
                   spacing_mm=t.spacing_mm, span_m=round(H - 2 * c, 4), shape="U",
                   formula=f"n = (ROUND(({fmt(H)} - 2c)/{fmt(s)}) + 1) x {t.per_layer} = {int(n)}; "
                           f"cut = leg {fmt(leg)} + hooks {fmt(hooks)} - 2x0.6d")
    if not spec.vertical_bars:
        rb.warnings.append("No vertical bars found for this column")
    if not spec.ties:
        rb.warnings.append("No ties/rings found for this column")
    return rb.rows, rb.warnings


def column_size_label(spec: ColumnSpec) -> str:
    return (f"{int(round(spec.length_m*1000))} x {int(round(spec.width_m*1000))} x H {spec.height_m:.3f} | "
            f"{bars_label(spec.vertical_bars) or '-'}")
