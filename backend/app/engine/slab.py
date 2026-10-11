"""Slab BBS — reproduces the '14th slab' sheet logic.

Reference (Slab S3, 4.9 x 5.35 x 0.175, cover 20):
  Short span T8@150 alt. bent up : a=c=MAX(10d,0.2)=0.2, b=Lx=4.9, e=0.42(D-2c)=0.057 -> 5.357 m
                                   n = ROUND((Ly-2c)/s)+1 = 36
  Long span  T8@175 alt. bent up : b=Ly=5.35 ...                                   n = ROUND((Lx-2c)/s)+1 = 29
  Short span top bar dist. end   : b=Lx, n = (ROUND((Ly/7)/s)+1) x edges(2)
  Continuous edge top bars       : zone 0.3 x L instead of L/7
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from app.engine.common import RowBuilder, fmt, xround
from app.models.schemas import BarRow, SlabLayer, SlabSpec, Standards


def _anch(std: Standards, dia: int) -> float:
    return max(10 * dia / 1000.0, std.slab_min_anchorage_m)


def _main(rb: RowBuilder, std: Standards, layer: Optional[SlabLayer], run: float, across: float,
          D: float, label: str) -> None:
    if not layer or layer.spacing_mm <= 0:
        return
    c = std.cover_slab_mm / 1000.0
    s = layer.spacing_mm / 1000.0
    a = _anch(std, layer.dia_mm)
    e = std.slab_bentup_factor * (D - 2 * c) if layer.bent_up else 0.0
    n = xround((across - 2 * c) / s) + 1
    kind = "Alt. Bent Up" if layer.bent_up else "Straight"
    rb.add(f"{label} Steel T{layer.dia_mm} @{int(layer.spacing_mm)} c/c {kind}", layer.dia_mm, n,
           a=round(a, 4), b=round(run, 4), c=round(a, 4), e=round(e, 4),
           spacing_mm=layer.spacing_mm, span_m=round(across, 4), shape="crank" if layer.bent_up else "straight",
           formula=f"n = ROUND(({fmt(across)} - 2c)/{fmt(s)}) + 1 = {int(n)}; a=c=MAX(10d,0.2)={fmt(a)}"
                   + (f"; bent-up extra 0.42(D-2c)={fmt(e)}" if e else ""))


def _top(rb: RowBuilder, std: Standards, layer: Optional[SlabLayer], run: float, across: float,
         fraction: float, label: str, edges: int) -> None:
    if not layer or layer.spacing_mm <= 0:
        return
    s = layer.spacing_mm / 1000.0
    a = _anch(std, layer.dia_mm)
    zone = across * fraction
    n = (xround(zone / s) + 1) * edges
    rb.add(f"{label} T{layer.dia_mm} @{int(layer.spacing_mm)} c/c", layer.dia_mm, n,
           a=round(a, 4), b=round(run, 4), c=round(a, 4),
           spacing_mm=layer.spacing_mm, span_m=round(zone, 4),
           formula=f"zone {fmt(fraction)} x {fmt(across)} = {fmt(zone)}; n = (ROUND({fmt(zone)}/{fmt(s)}) + 1) x {edges} edges = {int(n)}")


def compute_slab(spec: SlabSpec, std: Standards) -> Tuple[List[BarRow], List[str]]:
    rb = RowBuilder(std, spec.nos)
    Lx, Ly, D = spec.length_m, spec.width_m, spec.thickness_m
    _main(rb, std, spec.short_main, Lx, Ly, D, "Short Span")
    if spec.one_way and spec.long_main and not spec.long_main.bent_up:
        _main(rb, std, spec.long_main, Ly, Lx, D, "Dist.")
    else:
        _main(rb, std, spec.long_main, Ly, Lx, D, "Long Span")

    f_dist, f_cont = std.slab_dist_end_fraction, std.slab_cont_edge_fraction
    # edges: if both a discontinuous and a continuous layer exist for the same direction, one edge each
    short_edges = 1 if (spec.short_top_dist_end and spec.short_top_cont_edge) else 2
    long_edges = 1 if (spec.long_top_dist_end and spec.long_top_cont_edge) else 2
    _top(rb, std, spec.short_top_dist_end, Lx, Ly, f_dist, "Short Span Top Bar Dist. End", short_edges)
    _top(rb, std, spec.short_top_cont_edge, Lx, Ly, f_cont, "Short Span Top Bar Cont. Edge", short_edges)
    _top(rb, std, spec.long_top_dist_end, Ly, Lx, f_dist, "Long Span Top Bar Dist. End", long_edges)
    _top(rb, std, spec.long_top_cont_edge, Ly, Lx, f_cont, "Long Span Top Bar Cont. Edge", long_edges)

    for layer in spec.extra_top:
        if layer.spacing_mm > 0:
            _main(rb, std, SlabLayer(dia_mm=layer.dia_mm, spacing_mm=layer.spacing_mm, bent_up=False),
                  Lx, Ly, D, f"Extra Top {layer.note or ''}".strip())
    if not spec.short_main and not spec.long_main:
        rb.warnings.append("No main reinforcement found for this slab panel")
    return rb.rows, rb.warnings


def slab_size_label(spec: SlabSpec) -> str:
    sm = f"T{spec.short_main.dia_mm}@{int(spec.short_main.spacing_mm)}" if spec.short_main else "-"
    lm = f"T{spec.long_main.dia_mm}@{int(spec.long_main.spacing_mm)}" if spec.long_main else "-"
    return f"{spec.length_m:.3f} x {spec.width_m:.3f} x {int(round(spec.thickness_m*1000))} | Short {sm} | Long {lm}"
