"""Fit-out BOQ engine: FitoutItems -> ordered sections / lines / totals (the KR BOQ layout)."""
from __future__ import annotations

import math
from collections import OrderedDict
from typing import Dict, List, Optional, Sequence

from app.models.schemas import (
    BOQLine, BOQResult, BOQSection, BOQSummary, DIVISION_LABELS, FitoutItem, RoomRecord,
)

DIVISION_ORDER = ["preliminaries", "finishes", "joinery", "doors", "lighting", "ffe", "mep", "other"]
SECTION_ORDER = [
    "Preliminaries", "Floor Finishes", "Wall Finishes", "Ceilings", "Skirting & Trims", "Glazing & Partitions",
    "Joinery", "Doors", "Lighting", "Chairs", "Tables", "Loose Furniture", "Accessories", "MEP", "Other",
]
UNIT_DECIMALS = {"m2": 1, "lm": 1, "m3": 2, "kg": 1, "nos": 0, "item": 0, "ls": 0}


def item_ref(n: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA ..."""
    s = ""
    n += 1
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def round_qty(qty: float, unit: str) -> float:
    d = UNIT_DECIMALS.get(unit, 2)
    if d == 0:
        return float(math.ceil(qty - 1e-9)) if qty > 0 else 0.0
    f = 10 ** d
    return math.ceil(qty * f - 1e-9) / f if qty > 0 else 0.0


def _section_rank(section: str) -> int:
    try:
        return SECTION_ORDER.index(section)
    except ValueError:
        return len(SECTION_ORDER)


def compute_boq(items: Sequence[FitoutItem], rooms: Sequence[RoomRecord], currency: str = "AED",
                vat_pct: float = 5.0) -> BOQResult:
    warnings: List[str] = []
    grouped: "OrderedDict[tuple, List[FitoutItem]]" = OrderedDict()
    ordered = sorted(items, key=lambda it: (DIVISION_ORDER.index(it.division) if it.division in DIVISION_ORDER else 99,
                                            _section_rank(it.section), (it.code or "~"), it.description))
    for it in ordered:
        grouped.setdefault((it.division, it.section or "Other"), []).append(it)

    sections: List[BOQSection] = []
    seq = 0
    for (division, section), its in grouped.items():
        lines: List[BOQLine] = []
        qty_by_unit: Dict[str, float] = {}
        amount = 0.0
        for i, it in enumerate(its):
            seq += 1
            qty = round_qty(it.qty, it.unit)
            rate = it.rate if (it.rate is not None and it.rate > 0) else None
            amt = round(qty * rate, 2) if rate is not None else None
            if qty == 0:
                warnings.append(f"{it.code or it.description}: quantity is zero ({it.qty_basis}) - review")
            desc = it.description
            if it.size_label and it.size_label not in desc:
                desc = f"{desc} - {it.size_label}"
            lines.append(BOQLine(
                seq=seq, item_ref=item_ref(i), item_id=it.id, division=division, section=section, code=it.code,
                description=desc, unit=it.unit, qty=qty, rate=rate, amount=amt, qty_basis=it.qty_basis,
                rooms=list(it.rooms), confidence=it.confidence, evidence=list(it.evidence), source_sheet=it.source_sheet,
                formula=(f"{it.qty_basis}: {it.qty:g} {it.unit}" + (f" -> rounded {qty:g}" if qty != it.qty else "")
                         + (f"; amount = {qty:g} x {rate:g} = {amt:,.2f}" if amt is not None else "")),
            ))
            qty_by_unit[it.unit] = round(qty_by_unit.get(it.unit, 0.0) + qty, 3)
            amount += amt or 0.0
        sections.append(BOQSection(division=division, division_label=DIVISION_LABELS.get(division, division.upper()),
                                   section=section, lines=lines, qty_by_unit=qty_by_unit, amount=round(amount, 2)))

    div_rows: List[Dict] = []
    total_by_unit: Dict[str, float] = {}
    subtotal, priced, n_lines = 0.0, 0, 0
    for division in DIVISION_ORDER:
        secs = [s for s in sections if s.division == division]
        if not secs:
            continue
        amt = round(sum(s.amount for s in secs), 2)
        cnt = sum(len(s.lines) for s in secs)
        div_rows.append({"division": division, "label": DIVISION_LABELS.get(division, division.upper()),
                         "line_count": cnt, "amount": amt})
        subtotal += amt
        n_lines += cnt
        for s in secs:
            priced += sum(1 for l in s.lines if l.amount is not None)
            for u, q in s.qty_by_unit.items():
                total_by_unit[u] = round(total_by_unit.get(u, 0.0) + q, 3)
    vat = round(subtotal * vat_pct / 100.0, 2)
    summary = BOQSummary(currency=currency, vat_pct=vat_pct, divisions=div_rows, line_count=n_lines,
                         qty_by_unit=total_by_unit, priced_lines=priced, subtotal=round(subtotal, 2), vat=vat,
                         grand_total=round(subtotal + vat, 2))
    if priced and priced < n_lines:
        warnings.append(f"Only {priced} of {n_lines} lines have rates; amounts are partial")
    return BOQResult(sections=sections, rooms=list(rooms), summary=summary, warnings=warnings)
