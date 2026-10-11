"""Regex parsers for Indian structural drawing notation.

Examples handled:
  "2-T20", "2T20", "2 - Y16", "3-#12", "2 Nos 20mm dia", "4-20Ø", "2-T20 + 1-T16"
  "T8@100 c/c", "8 @ 150 C/C", "Y10@200", "2L-T8@100", "4L T8 @ 100 c/c"
  "230 x 750", "230X750", "300x450mm"
  "B1A", "FB-12", "C6", "S3", "L1", "SW2"
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.models.schemas import BarGroup

DIA_MARK = r"(?:T|Y|Ø|ø|Φ|φ|#|Fe|HYSD|TMT)?"
_GROUP_RX = re.compile(
    # count, then EITHER "nos"/"no." words, OR a dash/x separator, OR a bar mark glued to the dia (2T20),
    # then the diameter. A bare "4  8-T16" can no longer be read as 4 bars of 8 mm.
    rf"(?<![\d.])(\d{{1,2}})\s*(?:(?:nos?\.?|no\.?)\s*[-–]?\s*{DIA_MARK}|[-–x×]\s*{DIA_MARK}|(?:T|Y|Ø|ø|Φ|φ|#))"
    rf"\s*(\d{{1,2}})\s*(?:mm)?\s*(?:dia\.?|Ø|ø|Φ|φ)?(?![\d@xX×])",
    re.I,
)
_SPACING_RX = re.compile(
    rf"(?:(\d)\s*L\s*[-–]?\s*)?{DIA_MARK}\s*(\d{{1,2}})\s*(?:mm)?\s*(?:dia\.?)?\s*@\s*(\d{{2,3}})\s*(?:mm)?\s*(?:c/c|c\.c\.|c-c|ctrs?|centres?)?",
    re.I,
)
_SIZE_RX = re.compile(r"(?<![\d.])(\d{3,4})\s*[xX×]\s*(\d{3,4})(?:\s*(?:mm))?(?![\d])")
_SIZE3_RX = re.compile(r"(?<![\d.])(\d{3,4})\s*[xX×]\s*(\d{3,4})\s*[xX×]\s*(\d{3,4})")
_TAG_RX = re.compile(r"^(FB|PB|LB|SB|CB|TB|GB|B|FC|HC|PC|C|SW|S|L|W|ST|RW|CW)\s?-?\s?(\d{1,3})\s?([A-Z]?)(?:\s*\((\d+)\s*nos?\.?\))?$", re.I)
_MM_DIA_RX = re.compile(r"(\d{1,2})\s*mm", re.I)
VALID_DIAS = {6, 8, 10, 12, 16, 20, 25, 28, 32, 36, 40}


def parse_bar_groups(text: str) -> List[BarGroup]:
    """'2-T20 + 1-T16' -> [BarGroup(2,20), BarGroup(1,16)]. Ignores sizes like 230x750 and spacings."""
    if not text:
        return []
    cleaned = _SPACING_RX.sub(" ", text)
    cleaned = _SIZE3_RX.sub(" ", cleaned)
    cleaned = _SIZE_RX.sub(" ", cleaned)
    out: List[BarGroup] = []
    for m in _GROUP_RX.finditer(cleaned):
        count, dia = int(m.group(1)), int(m.group(2))
        if dia not in VALID_DIAS or count == 0 or count > 60:
            continue
        out.append(BarGroup(count=count, dia_mm=dia))
    return out


@dataclass
class SpacingCallout:
    dia_mm: int
    spacing_mm: float
    legs: int = 2
    raw: str = ""


def parse_spacing(text: str) -> Optional[SpacingCallout]:
    if not text:
        return None
    m = _SPACING_RX.search(text)
    if not m:
        return None
    legs = int(m.group(1)) if m.group(1) else 2
    dia, sp = int(m.group(2)), float(m.group(3))
    if dia not in VALID_DIAS or sp < 50 or sp > 600:
        return None
    return SpacingCallout(dia_mm=dia, spacing_mm=sp, legs=legs, raw=m.group(0).strip())


def parse_all_spacings(text: str) -> List[SpacingCallout]:
    out = []
    for m in _SPACING_RX.finditer(text or ""):
        legs = int(m.group(1)) if m.group(1) else 2
        dia, sp = int(m.group(2)), float(m.group(3))
        if dia in VALID_DIAS and 50 <= sp <= 600:
            out.append(SpacingCallout(dia_mm=dia, spacing_mm=sp, legs=legs, raw=m.group(0).strip()))
    return out


def parse_size_mm(text: str) -> Optional[Tuple[float, float]]:
    """'230 x 750' -> (230, 750) in mm."""
    m = _SIZE_RX.search(text or "")
    if not m:
        return None
    a, b = float(m.group(1)), float(m.group(2))
    if a < 75 or b < 75 or a > 6000 or b > 6000:
        return None
    return a, b


def parse_size3_mm(text: str) -> Optional[Tuple[float, float, float]]:
    m = _SIZE3_RX.search(text or "")
    if not m:
        return None
    return float(m.group(1)), float(m.group(2)), float(m.group(3))


@dataclass
class MemberTag:
    prefix: str
    number: int
    suffix: str
    kind: str  # beam | column | slab | wall | stair | unknown
    nos: Optional[int] = None

    @property
    def tag(self) -> str:
        return f"{self.prefix}{self.number}{self.suffix}"


_PREFIX_KIND = {
    "B": "beam", "FB": "beam", "PB": "beam", "LB": "beam", "SB": "beam", "CB": "beam", "TB": "beam", "GB": "beam",
    "C": "column", "FC": "column", "HC": "column", "PC": "column",
    "S": "slab", "SW": "wall", "W": "wall", "RW": "wall", "CW": "wall", "L": "column", "ST": "stair",
}


def parse_member_tag(text: str) -> Optional[MemberTag]:
    m = _TAG_RX.match((text or "").strip())
    if not m:
        return None
    prefix = m.group(1).upper()
    return MemberTag(prefix=prefix, number=int(m.group(2)), suffix=(m.group(3) or "").upper(),
                     kind=_PREFIX_KIND.get(prefix, "unknown"),
                     nos=int(m.group(4)) if m.group(4) else None)


def parse_dia_mm(text: str) -> Optional[int]:
    m = _MM_DIA_RX.search(text or "")
    if m and int(m.group(1)) in VALID_DIAS:
        return int(m.group(1))
    m2 = re.search(rf"{DIA_MARK}\s*(\d{{1,2}})\b", text or "")
    if m2 and int(m2.group(1)) in VALID_DIAS and re.search(r"[TYØøΦφ#]", text or ""):
        return int(m2.group(1))
    return None


def looks_like_schedule_header(text: str) -> bool:
    t = (text or "").lower()
    keys = ["beam", "column", "size", "bottom", "top", "stirrup", "extra", "schedule", "reinforcement",
            "main", "dist", "spacing", "dia", "ties", "links", "remarks", "mark", "level", "section"]
    return sum(k in t for k in keys) >= 1 and len(t) < 40
