"""Beam BBS — reproduces the '14th Beam' sheet logic.

Reference rows (B1A, 230 x 750, span 2.45, cover 30, Ld 39):
  Main Bar Bottom 2-T20 : a=(39+10)*20/1000=0.98, b=2.45, c=0.98 -> 4.41 m
  Left/Right Extra      : b = L/3 (+ anchorage at an end support)
  Bottom curtail        : b = L - 2 x 0.1L
  Stirrups T8@100 sides : zone L/3 each end, n = (ROUND((L/3 - 0.05)/s) + 1) x 2
  Stirrups T8@150 mid   : zone L - 2L/3,       n =  ROUND(zone / s) - 1
  Stirrup cut length    : 2(B-2c) + 2(D-2c) + 2 x 10d - 5 x 0.6d
  SFR                   : 2 bars per face, length L (deep beams only)
"""
from __future__ import annotations

from typing import List, Tuple

from app.engine.common import (
    RowBuilder, anchorage_continuous, anchorage_end, bars_label, fmt, xround,
)
from app.models.schemas import BarGroup, BarRow, BeamSpec, Standards, StirrupZone


def _anch(std: Standards, dia: int, support: str):
    if support == "end":
        return anchorage_end(std, dia), 1
    return anchorage_continuous(std, dia), 0


def _main_bars(rb: RowBuilder, std: Standards, spec: BeamSpec, groups: List[BarGroup], label: str) -> None:
    for g in groups:
        if g.count <= 0:
            continue
        a, ca = _anch(std, g.dia_mm, spec.left_support)
        c, cc = _anch(std, g.dia_mm, spec.right_support)
        rb.add(
            f"{label} {g.count}-T{g.dia_mm}",
            g.dia_mm, g.count,
            a=round(a, 4), b=spec.span_m, c=round(c, 4),
            bend_corners=ca + cc,
            shape="L" if (ca + cc) else "straight",
            formula=(
                f"a={'(Ld+10)d' if ca else 'MAX(10d,0.3)'}={fmt(a)}, b=L={fmt(spec.span_m)}, "
                f"c={'(Ld+10)d' if cc else 'MAX(10d,0.3)'}={fmt(c)}"
            ),
        )


def _extra_bars(rb: RowBuilder, std: Standards, spec: BeamSpec, groups: List[BarGroup], side: str) -> None:
    support = spec.left_support if side == "Left" else spec.right_support
    zone = spec.span_m * std.extra_bar_span_fraction
    for g in groups:
        if g.count <= 0:
            continue
        anch, corners = _anch(std, g.dia_mm, support)
        if side == "Left":
            rb.add(f"Main Bar Left Extra {g.count}-T{g.dia_mm}", g.dia_mm, g.count,
                   a=round(anch, 4), b=round(zone, 4), bend_corners=corners,
                   shape="L" if corners else "straight",
                   formula=f"anchorage {fmt(anch)} + L/3 {fmt(zone)}")
        else:
            rb.add(f"Main Bar Right Extra {g.count}-T{g.dia_mm}", g.dia_mm, g.count,
                   b=round(zone, 4), c=round(anch, 4), bend_corners=corners,
                   shape="L" if corners else "straight",
                   formula=f"L/3 {fmt(zone)} + anchorage {fmt(anch)}")


def _stirrups(rb: RowBuilder, std: Standards, spec: BeamSpec) -> None:
    c = std.cover_beam_mm / 1000.0
    L = spec.span_m
    end_zone = L * std.end_zone_span_fraction
    mid_zone = max(L - 2 * end_zone, 0.0)
    zones = spec.stirrups
    has_end = any(z.zone == "end" for z in zones)
    has_mid = any(z.zone == "mid" for z in zones)
    for z in zones:
        s = z.spacing_mm / 1000.0
        if s <= 0:
            rb.warnings.append("Stirrup spacing missing; row skipped")
            continue
        sets = max(z.legs // 2, 1)  # 4-legged = 2 closed stirrups per position
        if z.zone == "end" or (z.zone == "full" and has_mid and not has_end):
            n = (xround((end_zone - std.stirrup_end_offset_m) / s) + 1) * 2
            desc = f"Stirrups {z.legs}L T{z.dia_mm} @{int(z.spacing_mm)} c/c Sides (L/3 both ends)"
            span = end_zone
            formula = f"n = (ROUND(({fmt(end_zone)} - {std.stirrup_end_offset_m})/{fmt(s)}) + 1) x 2 = {int(n)}"
        elif z.zone == "mid":
            n = max(xround(mid_zone / s) - 1, 0)
            desc = f"Stirrups {z.legs}L T{z.dia_mm} @{int(z.spacing_mm)} c/c Mid"
            span = mid_zone
            formula = f"n = ROUND({fmt(mid_zone)}/{fmt(s)}) - 1 = {int(n)}"
        else:  # full length, single spacing
            n = xround((L - 2 * std.stirrup_end_offset_m) / s) + 1
            desc = f"Stirrups {z.legs}L T{z.dia_mm} @{int(z.spacing_mm)} c/c"
            span = L
            formula = f"n = ROUND(({fmt(L)} - 2x{std.stirrup_end_offset_m})/{fmt(s)}) + 1 = {int(n)}"
        a = (spec.width_m - 2 * c) * 2
        b = (spec.depth_m - 2 * c) * 2
        hooks = z.dia_mm * std.hook_length_d * 2 / 1000.0
        rb.add(desc, z.dia_mm, n * sets,
               a=round(a, 4), b=round(b, 4), c=round(hooks, 4),
               bend_corners=std.stirrup_corners, spacing_mm=z.spacing_mm, span_m=round(span, 4),
               shape="stirrup",
               formula=f"{formula}; cut = 2(B-2c) {fmt(a)} + 2(D-2c) {fmt(b)} + hooks {fmt(hooks)} - {std.stirrup_corners}x0.6d")


def compute_beam(spec: BeamSpec, std: Standards) -> Tuple[List[BarRow], List[str]]:
    rb = RowBuilder(std, spec.nos)
    _main_bars(rb, std, spec, spec.bottom_bars, "Main Bar Bottom")
    for g in spec.bottom_curtail:
        if g.count > 0:
            b = spec.span_m - 2 * spec.span_m * std.curtail_fraction
            rb.add(f"Bottom Curtail {g.count}-T{g.dia_mm}", g.dia_mm, g.count, b=round(b, 4),
                   formula=f"L - 2 x {std.curtail_fraction}L = {fmt(b)}")
    _main_bars(rb, std, spec, spec.top_bars, "Main Bar Top")
    _extra_bars(rb, std, spec, spec.extra_top_left, "Left")
    _extra_bars(rb, std, spec, spec.extra_top_right, "Right")
    for g in spec.extra_bottom_mid:
        if g.count > 0:
            b = spec.span_m * 0.6
            rb.add(f"Bottom Extra Mid {g.count}-T{g.dia_mm}", g.dia_mm, g.count, b=round(b, 4),
                   formula=f"0.6 L = {fmt(b)}")
    _stirrups(rb, std, spec)
    sfr = spec.sfr_bars
    if not sfr and spec.depth_m >= std.sfr_min_depth_m:
        sfr = [BarGroup(count=2, dia_mm=8, note="auto: depth >= 750")]
        rb.warnings.append("Side face reinforcement assumed 2-T8 per face (depth >= 750 mm)")
    for g in sfr:
        if g.count > 0:
            rb.add(f"SFR {g.count}-T{g.dia_mm} each face", g.dia_mm, g.count * 2, b=spec.span_m,
                   formula=f"{g.count} per face x 2 faces, length L = {fmt(spec.span_m)}")
    if not spec.bottom_bars and not spec.top_bars:
        rb.warnings.append("No main bars found for this beam")
    if not spec.stirrups:
        rb.warnings.append("No stirrups found for this beam")
    return rb.rows, rb.warnings


def beam_size_label(spec: BeamSpec) -> str:
    return (f"{spec.span_m:.3f} x {int(round(spec.width_m*1000))} x {int(round(spec.depth_m*1000))} | "
            f"Bot {bars_label(spec.bottom_bars) or '-'} | Top {bars_label(spec.top_bars) or '-'}")


__all__ = ["compute_beam", "beam_size_label", "StirrupZone"]
