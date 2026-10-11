"""Facade: members -> BBS rows -> dia-wise summary (the Excel 'Summary' tab)."""
from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple

from app.engine.beam import beam_size_label, compute_beam
from app.engine.column import column_size_label, compute_column
from app.engine.slab import compute_slab, slab_size_label
from app.engine.stair import compute_stair, stair_size_label
from app.engine.wall import compute_wall, wall_size_label
from app.models.schemas import (
    BarRow, BBSResult, BBSSummary, BeamSpec, CategorySummary, ColumnSpec,
    MemberResult, SlabSpec, StairSpec, Standards, WallSpec,
)

CATEGORY_LABELS = {
    "beam": "Beam",
    "slab": "Slab",
    "column": "Column",
    "wall": "NSW / Wall",
    "stair": "Staircase",
}
CATEGORY_ORDER = ["beam", "slab", "column", "wall", "stair"]


def compute_member(member, std: Standards) -> MemberResult:
    if isinstance(member, BeamSpec):
        rows, warnings = compute_beam(member, std)
        label = beam_size_label(member)
    elif isinstance(member, SlabSpec):
        rows, warnings = compute_slab(member, std)
        label = slab_size_label(member)
    elif isinstance(member, ColumnSpec):
        rows, warnings = compute_column(member, std)
        label = column_size_label(member)
    elif isinstance(member, WallSpec):
        rows, warnings = compute_wall(member, std)
        label = wall_size_label(member)
    elif isinstance(member, StairSpec):
        rows, warnings = compute_stair(member, std)
        label = stair_size_label(member)
    else:  # pragma: no cover
        raise TypeError(f"Unsupported member type: {type(member)!r}")

    by_dia: Dict[int, float] = {}
    for r in rows:
        by_dia[r.dia_mm] = round(by_dia.get(r.dia_mm, 0.0) + r.weight_kg, 3)
    return MemberResult(
        member_id=member.id,
        kind=member.kind,
        tag=member.tag,
        nos=member.nos,
        size_label=label,
        rows=rows,
        weight_kg=round(sum(r.weight_kg for r in rows), 3),
        weight_by_dia_kg=by_dia,
        confidence=member.confidence,
        warnings=warnings,
    )


def summarise(results: Sequence[MemberResult], std: Standards, level: str) -> BBSSummary:
    dias = list(std.diameters_in_summary)
    for r in results:
        for d in r.weight_by_dia_kg:
            if d not in dias:
                dias.append(d)
    dias.sort()
    cats: List[CategorySummary] = []
    total_by_dia: Dict[int, float] = {d: 0.0 for d in dias}
    for kind in CATEGORY_ORDER:
        members = [r for r in results if r.kind == kind]
        if not members:
            continue
        by_dia = {d: 0.0 for d in dias}
        for m in members:
            for d, kg in m.weight_by_dia_kg.items():
                by_dia[d] += kg / 1000.0
        by_dia_r = {d: round(v, 3) for d, v in by_dia.items()}
        for d, v in by_dia.items():
            total_by_dia[d] += v
        cats.append(CategorySummary(
            category=CATEGORY_LABELS[kind],
            weight_by_dia_t=by_dia_r,
            total_t=round(sum(by_dia.values()), 3),
            member_count=len(members),
        ))
    total_r = {d: round(v, 3) for d, v in total_by_dia.items()}
    return BBSSummary(level=level, categories=cats, total_by_dia_t=total_r,
                      grand_total_t=round(sum(total_by_dia.values()), 3))


def compute_bbs(members: Iterable, std: Standards, level: str = "") -> BBSResult:
    results = [compute_member(m, std) for m in members]
    return BBSResult(standards=std, members=results, summary=summarise(results, std, level))
