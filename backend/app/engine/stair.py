"""Staircase BBS — follows the 'Staircase' sheet logic (waist slab flights + landings).

Per flight:
  inclined length = sqrt(going^2 + rise^2)
  Main span steel : cut = landing_a + inclined + landing_b + Ld x d (dowel) - bends
                    n   = ROUND((W - 2c)/s) + 1
  Dist. steel     : cut = W - 2c ; n = ROUND((inclined + landings)/s) + 1
"""
from __future__ import annotations

import math
from typing import List, Tuple

from app.engine.common import RowBuilder, fmt, lap_length, xround
from app.models.schemas import BarRow, StairSpec, Standards


def compute_stair(spec: StairSpec, std: Standards) -> Tuple[List[BarRow], List[str]]:
    rb = RowBuilder(std, spec.nos)
    c = std.cover_stair_mm / 1000.0
    if not spec.flights:
        rb.warnings.append("No flights defined for this staircase")
    for fl in spec.flights:
        inclined = math.sqrt(fl.going_m ** 2 + fl.rise_m ** 2)
        total_run = fl.landing_a_m + inclined + fl.landing_b_m
        if fl.main and fl.main.spacing_mm > 0:
            s = fl.main.spacing_mm / 1000.0
            n = xround((fl.width_m - 2 * c) / s) + 1
            lap = lap_length(std, fl.main.dia_mm)
            rb.add(f"{fl.name}: Main Span Steel T{fl.main.dia_mm} @{int(fl.main.spacing_mm)} c/c", fl.main.dia_mm, n,
                   a=round(fl.landing_a_m, 4), b=round(inclined, 4), c=round(fl.landing_b_m, 4), d=round(lap, 4),
                   bend_corners=2, spacing_mm=fl.main.spacing_mm, span_m=round(fl.width_m, 4), shape="crank",
                   formula=f"inclined = sqrt({fmt(fl.going_m)}^2 + {fmt(fl.rise_m)}^2) = {fmt(inclined)}; "
                           f"n = ROUND(({fmt(fl.width_m)} - 2c)/{fmt(s)}) + 1 = {int(n)}; + dowel Ld d {fmt(lap)}")
        else:
            rb.warnings.append(f"{fl.name}: main steel missing")
        if fl.dist and fl.dist.spacing_mm > 0:
            s = fl.dist.spacing_mm / 1000.0
            n = xround(total_run / s) + 1
            rb.add(f"{fl.name}: Dist. Steel T{fl.dist.dia_mm} @{int(fl.dist.spacing_mm)} c/c", fl.dist.dia_mm, n,
                   b=round(fl.width_m - 2 * c, 4), spacing_mm=fl.dist.spacing_mm, span_m=round(total_run, 4),
                   formula=f"n = ROUND({fmt(total_run)}/{fmt(s)}) + 1 = {int(n)}; cut = W - 2c")
        else:
            rb.warnings.append(f"{fl.name}: distribution steel missing")
    return rb.rows, rb.warnings


def stair_size_label(spec: StairSpec) -> str:
    if not spec.flights:
        return "-"
    f0 = spec.flights[0]
    return f"{len(spec.flights)} flight(s) | W {f0.width_m:.3f} | waist {int(round(f0.waist_m*1000))}"
