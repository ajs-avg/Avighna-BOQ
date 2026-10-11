"""Non-structural / RCC wall (pardi, upstand) BBS — reproduces the '13th To 14th NSW' sheet logic.

  Vertical   : cut = (H - c) + Ld x d (starter lap)    ; n = (ROUND((L-2c)/s) + 1) x faces
  Horizontal : cut = L + 2 x Ld x d                     ; n = (ROUND((H-2c)/s) + 1) x faces
"""
from __future__ import annotations

from typing import List, Tuple

from app.engine.common import RowBuilder, fmt, lap_length, xround
from app.models.schemas import BarRow, Standards, WallSpec


def compute_wall(spec: WallSpec, std: Standards) -> Tuple[List[BarRow], List[str]]:
    rb = RowBuilder(std, spec.nos)
    c = std.cover_wall_mm / 1000.0
    L, H = spec.length_m, spec.height_m
    faces = max(1, min(spec.faces, 2))
    face_lbl = "Double Wall" if faces == 2 else "Single Wall"

    if spec.vertical and spec.vertical.spacing_mm > 0:
        v = spec.vertical
        s = v.spacing_mm / 1000.0
        n = (xround((L - 2 * c) / s) + 1) * faces
        lap = lap_length(std, v.dia_mm) if spec.starter_lap else 0.0
        hooks = 0.0 if spec.starter_lap else 0.1 * 2
        rb.add(f"Main Vert. Steel T{v.dia_mm} @{int(v.spacing_mm)} c/c {face_lbl}", v.dia_mm, n,
               a=round(lap, 4), b=round(H - c, 4), c=round(hooks, 4),
               bend_corners=1 if spec.starter_lap else 2,
               spacing_mm=v.spacing_mm, span_m=round(L, 4), shape="L",
               formula=f"n = (ROUND(({fmt(L)} - 2c)/{fmt(s)}) + 1) x {faces} = {int(n)}; cut = (H-c) {fmt(H-c)} + lap {fmt(lap)}")
    else:
        rb.warnings.append("No vertical steel found for this wall")

    if spec.horizontal and spec.horizontal.spacing_mm > 0:
        h = spec.horizontal
        s = h.spacing_mm / 1000.0
        n = (xround((H - 2 * c) / s) + 1) * faces
        lap = lap_length(std, h.dia_mm)
        rb.add(f"Dist. Steel T{h.dia_mm} @{int(h.spacing_mm)} c/c {'Both Sides' if faces == 2 else ''}".strip(),
               h.dia_mm, n,
               a=round(lap, 4), b=round(L, 4), c=round(lap, 4), bend_corners=2,
               spacing_mm=h.spacing_mm, span_m=round(H, 4), shape="U",
               formula=f"n = (ROUND(({fmt(H)} - 2c)/{fmt(s)}) + 1) x {faces} = {int(n)}; cut = L {fmt(L)} + 2 x Ld d {fmt(lap)}")
    else:
        rb.warnings.append("No horizontal/distribution steel found for this wall")
    return rb.rows, rb.warnings


def wall_size_label(spec: WallSpec) -> str:
    v = f"T{spec.vertical.dia_mm}@{int(spec.vertical.spacing_mm)}" if spec.vertical else "-"
    return f"{spec.length_m:.3f} x {int(round(spec.thickness_m*1000))} thk x H {spec.height_m:.3f} | Vert {v}"
