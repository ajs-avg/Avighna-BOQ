"""A format-independent inventory of what is written on a sheet.

Both the DXF reader and the PDF reader produce a SheetInventory; the intelligence
layer (regex + Gemini) consumes it. Coordinates are in the sheet's own units with
y pointing UP (DXF convention); PDF y values are flipped on ingestion.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional


@dataclass
class TextItem:
    text: str
    x: float
    y: float
    w: float = 0.0
    h: float = 0.0
    layer: str = ""
    kind: str = "text"  # text | mtext | attrib | dimension | block
    rotation: float = 0.0

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


@dataclass
class SheetInventory:
    source: str
    page_no: int = 1
    layout: str = "Model"
    width: float = 0.0
    height: float = 0.0
    units_hint: str = "unknown"
    texts: List[TextItem] = field(default_factory=list)
    layers: List[str] = field(default_factory=list)
    entity_counts: Dict[str, int] = field(default_factory=dict)
    block_names: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    # ---------------------------------------------------------------- helpers
    def add(self, item: TextItem) -> None:
        t = (item.text or "").strip()
        if not t:
            return
        item.text = re.sub(r"\s+", " ", t)
        self.texts.append(item)

    def find(self, pattern: str, flags: int = re.I) -> List[TextItem]:
        rx = re.compile(pattern, flags)
        return [t for t in self.texts if rx.search(t.text)]

    def all_text(self) -> str:
        return "\n".join(t.text for t in self.texts)

    def unique_strings(self) -> List[str]:
        seen, out = set(), []
        for t in self.texts:
            if t.text not in seen:
                seen.add(t.text)
                out.append(t.text)
        return out

    def sorted_reading_order(self) -> List[TextItem]:
        """Top-to-bottom, left-to-right (y up => larger y first)."""
        return sorted(self.texts, key=lambda t: (-round(t.y / max(self.row_tolerance(), 1e-6)), t.x))

    def row_tolerance(self) -> float:
        hs = [t.h for t in self.texts if t.h > 0]
        if not hs:
            return 2.5
        hs.sort()
        return max(hs[len(hs) // 2] * 0.6, 1e-3)

    def to_prompt_text(self, max_items: int = 1800) -> str:
        """Compact, LLM-friendly listing: one text per line with normalised 0-1000 coords."""
        if not self.texts:
            return "(no machine-readable text on this sheet)"
        w = self.width or max((t.x + t.w) for t in self.texts) or 1.0
        h = self.height or max((t.y + t.h) for t in self.texts) or 1.0
        lines = []
        for t in self.sorted_reading_order()[:max_items]:
            nx = int(1000 * t.x / w) if w else 0
            ny = int(1000 * (1 - t.y / h)) if h else 0  # 0 = top
            layer = f" [{t.layer}]" if t.layer and t.layer != "0" else ""
            lines.append(f"({nx:4d},{ny:4d}){layer} {t.text}")
        extra = len(self.texts) - max_items
        if extra > 0:
            lines.append(f"... {extra} more text items omitted")
        return "\n".join(lines)

    def summary(self) -> Dict[str, object]:
        return {
            "source": self.source, "page_no": self.page_no, "layout": self.layout,
            "width": self.width, "height": self.height, "units_hint": self.units_hint,
            "text_count": len(self.texts), "layers": self.layers[:200],
            "entity_counts": self.entity_counts, "block_names": self.block_names[:100],
            "notes": self.notes,
        }


NUMERIC_RX = re.compile(r"^-?\d+(?:\.\d+)?$")


def numeric_items(items: Iterable[TextItem]) -> List[TextItem]:
    return [t for t in items if NUMERIC_RX.match(t.text.replace(",", ""))]


def guess_units(inv: SheetInventory) -> str:
    """Infer drawing units from the magnitude of numeric dimension strings."""
    vals = []
    for t in numeric_items(inv.texts):
        try:
            vals.append(abs(float(t.text.replace(",", ""))))
        except ValueError:
            pass
    vals = [v for v in vals if v > 0]
    if not vals:
        return inv.units_hint or "unknown"
    vals.sort()
    median = vals[len(vals) // 2]
    if median >= 400:
        return "mm"
    if median >= 40:
        return "cm"
    if median < 40:
        return "m"
    return "unknown"


def to_metres(value: float, units: str) -> Optional[float]:
    if units == "mm":
        return value / 1000.0
    if units == "cm":
        return value / 100.0
    if units == "m":
        return value
    return None
