"""Shared arithmetic helpers that mirror the Excel formulas in Avighna's BBS sheets."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.models.schemas import BarGroup, BarRow, Standards


def xround(value: float, digits: int = 0) -> float:
    """Excel ROUND(): half away from zero (Python's round() is banker's rounding)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0.0
    factor = 10 ** digits
    if value >= 0:
        return math.floor(value * factor + 0.5) / factor
    return -math.floor(-value * factor + 0.5) / factor


def fmt(v: float, nd: int = 3) -> str:
    return f"{v:.{nd}f}".rstrip("0").rstrip(".") if v != int(v) else str(int(v))


def bars_label(groups: List[BarGroup]) -> str:
    return " + ".join(f"{g.count}-T{g.dia_mm}" for g in groups if g.count > 0)


@dataclass
class RowBuilder:
    """Accumulates BarRow objects for one member and keeps the running sequence."""

    standards: Standards
    members: int
    rows: List[BarRow] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add(
        self,
        description: str,
        dia_mm: int,
        bars_per_member: float,
        *,
        a: float = 0.0,
        b: float = 0.0,
        c: float = 0.0,
        d: float = 0.0,
        e: float = 0.0,
        f: float = 0.0,
        g: float = 0.0,
        bend_corners: int = 0,
        spacing_mm: Optional[float] = None,
        span_m: Optional[float] = None,
        shape: str = "straight",
        formula: str = "",
    ) -> BarRow:
        if bars_per_member <= 0:
            self.warnings.append(f"'{description}' has zero bars and was skipped")
        gross = a + b + c + d + e + f + g
        deduction = dia_mm * bend_corners * self.standards.bend_deduction_d / 1000.0
        cut = max(gross - deduction, 0.0)
        total_bars = self.members * bars_per_member
        weight = total_bars * cut * self.standards.unit_weight(dia_mm)
        row = BarRow(
            seq=len(self.rows) + 1,
            description=description,
            dia_mm=dia_mm,
            members=self.members,
            bars_per_member=bars_per_member,
            total_bars=total_bars,
            spacing_mm=spacing_mm,
            span_m=span_m,
            a=a, b=b, c=c, d=d, e=e, f=f, g=g,
            bend_corners=bend_corners,
            cut_length_m=round(cut, 4),
            weight_kg=round(weight, 3),
            formula=formula or (
                f"cut = {fmt(gross)}"
                + (f" - {bend_corners}x0.6x{dia_mm}/1000" if bend_corners else "")
                + f" = {fmt(cut)} m; wt = {self.members} x {fmt(bars_per_member)} x {fmt(cut)} x {self.standards.unit_weight(dia_mm)} = {fmt(weight)} kg"
            ),
            shape=shape,
        )
        self.rows.append(row)
        return row

    def totals(self) -> Dict[int, float]:
        out: Dict[int, float] = {}
        for r in self.rows:
            out[r.dia_mm] = round(out.get(r.dia_mm, 0.0) + r.weight_kg, 3)
        return out


def anchorage_end(std: Standards, dia_mm: int) -> float:
    """Full L-bend anchorage into a support: (Ld + 10) x d."""
    return (std.ld_factor + std.anchorage_extra_d) * dia_mm / 1000.0


def anchorage_continuous(std: Standards, dia_mm: int) -> float:
    """Straight extension past a continuous support: MAX(10d, 0.3 m)."""
    return max(10 * dia_mm / 1000.0, std.min_straight_anchorage_m)


def lap_length(std: Standards, dia_mm: int) -> float:
    return std.ld_factor * dia_mm / 1000.0


def hook_length(std: Standards, dia_mm: int) -> float:
    return std.hook_length_d * dia_mm / 1000.0
