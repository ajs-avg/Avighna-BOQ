"""Review questions from a structural read, each with a highlighted crop of the drawing.

Every disagreement the reader found (plan vs schedule, a default it had to apply, a
shape with no name) and every measuring rule the drawing leaves open (who owns a
corner, where a beam stops at a pardi, who gets the concrete where the slab sits on a
beam) becomes one plain-English question. Each option carries the exact element edits
it would make, so answering is deterministic: the AI only maps a typed sentence onto
one of these options (or onto a typed number), and a person confirms before anything
changes. See app/decisions.py.
"""
from __future__ import annotations

import io
import math
import re
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LineString, Point, Polygon

from app.extract.structural.config import DEFAULT_CONFIG, StructuralConfig
from app.extract.structural.reader import StructuralReadResult
from app.models.schemas import (CustomField, MeasurementExtraction, QuestionChange, QuestionCustom,
                                QuestionOption, ReviewQuestion, SlabEl, new_id)

AMBER = (230, 140, 0)
RED = (210, 30, 30)
BLUE = (40, 90, 200)
GREEN = (26, 140, 55)

_FONT_PATHS = {
    "bold": ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"),
    "regular": ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Helvetica.ttc"),
}


def _font(size: int, bold: bool = False):
    for p in _FONT_PATHS["bold" if bold else "regular"]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def _mm(v_m: float) -> int:
    return int(round(v_m * 1000))


def _join(tags: Sequence[str]) -> str:
    tags = list(dict.fromkeys(tags))
    if len(tags) <= 1:
        return "".join(tags)
    return ", ".join(tags[:-1]) + " and " + tags[-1]


# =============================================================================
# The crop: real linework around the part being asked about, with that part lit up
# =============================================================================
class Highlight:
    def __init__(self, kind: str, color, *, geom=None, width: float = 0, poly=None, bbox=None,
                 at=None, radius: float = 0, label: str = "", dashed_to=None):
        self.kind, self.color = kind, color
        self.geom, self.width, self.poly, self.bbox = geom, width, poly, bbox
        self.at, self.radius, self.label, self.dashed_to = at, radius, label, dashed_to

    def shape(self):
        if self.kind == "beam":
            return LineString(self.geom).buffer(self.width / 2, cap_style=2)
        if self.kind == "poly":
            return Polygon(self.poly).buffer(0)
        if self.kind == "rect":
            x0, y0, x1, y1 = self.bbox
            return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
        if self.kind == "circle":
            return Point(self.at).buffer(self.radius)
        if self.kind == "dash":
            return LineString([self.at, self.dashed_to]).buffer(50)
        return None


def _window(hl: Sequence[Highlight], focus: Optional[Sequence[Highlight]] = None, margin: float = 1700,
            min_w: float = 5600, aspect: float = 880 / 600) -> List[float]:
    shapes = [h.shape() for h in (focus or hl)]
    shapes = [s for s in shapes if s is not None and not s.is_empty]
    xs0, ys0, xs1, ys1 = zip(*[s.bounds for s in shapes])
    x0, y0, x1, y1 = min(xs0) - margin, min(ys0) - margin, max(xs1) + margin, max(ys1) + margin
    w, h = max(x1 - x0, min_w), max(y1 - y0, min_w / aspect)
    if w / h < aspect:
        w = h * aspect
    else:
        h = w / aspect
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]


def _dashed(dr: ImageDraw.ImageDraw, pts, fill, width: int, on: float = 7, off: float = 4) -> None:
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        L = math.hypot(xb - xa, yb - ya)
        if L < 0.5:
            continue
        ux, uy = (xb - xa) / L, (yb - ya) / L
        d = 0.0
        while d < L:
            e = min(d + on, L)
            dr.line([(xa + ux * d, ya + uy * d), (xa + ux * e, ya + uy * e)], fill=fill, width=width)
            d = e + off


def render_crop(res: StructuralReadResult, highlights: Sequence[Highlight], cfg: StructuralConfig = DEFAULT_CONFIG,
                focus: Optional[Sequence[Highlight]] = None, px_w: int = 880, px_h: int = 600) -> bytes:
    win = _window(highlights, focus, aspect=px_w / px_h)
    x0, y0, x1, y1 = win
    sc = px_w / (x1 - x0)

    def P(x: float, y: float) -> Tuple[float, float]:
        return ((x - x0) * sc, (y1 - y) * sc)

    def visible(bx0, by0, bx1, by1) -> bool:
        return not (bx1 < x0 or bx0 > x1 or by1 < y0 or by0 > y1)

    im = Image.new("RGB", (px_w, px_h), (255, 255, 255))
    dr = ImageDraw.Draw(im, "RGBA")

    # --- the drawing itself, greyed: slab lines, beam edges (dashed, as drawn), column hatches
    for p in res.plan_prims:
        pts = p.points()
        xs = [q[0] for q in pts]
        ys = [q[1] for q in pts]
        if not visible(min(xs), min(ys), max(xs), max(ys)):
            continue
        px = [P(*q) for q in pts]
        if p.layer in cfg.beam_line_layers and p.aci in cfg.beam_line_aci:
            _dashed(dr, px, (95, 95, 95, 255), 2)
        elif p.layer in cfg.beam_line_layers:
            dr.line(px, fill=(175, 175, 175, 255), width=1)
        else:
            dr.line(px, fill=(165, 165, 165, 255), width=1)
    for h in res.hatches:
        bx = h.bbox
        if not visible(*bx):
            continue
        for pl in h.polys:
            if len(pl) >= 3:
                dr.polygon([P(*q) for q in pl], fill=(70, 70, 70, 215))
    text_layers = set(cfg.beam_tag_layers) | set(cfg.beam_size_layers) | set(cfg.column_tag_layers) \
        | set(cfg.column_size_layers) | set(cfg.slab_tag_layers)
    for t in res.plan_texts:
        if not (x0 <= t.cx <= x1 and y0 <= t.cy <= y1):
            continue
        if t.layer not in text_layers and "PARDI" not in t.text.upper():
            continue
        size = int(max(10, min(15, t.h * sc * 0.9)))
        f = _font(size)
        txt = t.text.replace("\n", " ").strip()[:28]
        cx, cy = P(t.cx, t.cy)
        if 60 < (t.rot % 180) < 120:  # vertical label: draw sideways
            w = int(dr.textlength(txt, font=f)) + 4
            tmp = Image.new("RGBA", (w, size + 6), (255, 255, 255, 0))
            ImageDraw.Draw(tmp).text((2, 1), txt, font=f, fill=(85, 85, 85, 255))
            tmp = tmp.rotate(90, expand=True)
            im.paste(tmp, (int(cx - tmp.width / 2), int(cy - tmp.height / 2)), tmp)
        else:
            dr.text((cx, cy), txt, font=f, fill=(85, 85, 85, 255), anchor="mm")

    # --- the part being asked about
    labels: List[Tuple[Tuple[float, float], str, tuple]] = []
    for h in highlights:
        c = h.color
        if h.kind in ("beam", "poly", "rect"):
            shp = h.shape()
            geoms = getattr(shp, "geoms", [shp])
            for g in geoms:
                if g.is_empty:
                    continue
                ring = [P(*q) for q in g.exterior.coords]
                alpha = 70 if h.kind == "poly" else 120
                dr.polygon(ring, fill=c + (alpha,))
                dr.line(ring + [ring[0]], fill=c + (255,), width=3)
            if h.label:
                anchor = shp.representative_point() if h.kind != "beam" else LineString(h.geom).interpolate(0.5, normalized=True)
                labels.append((P(anchor.x, anchor.y), h.label, c))
        elif h.kind == "circle":
            cx, cy = P(*h.at)
            r = h.radius * sc
            dr.ellipse([cx - r, cy - r, cx + r, cy + r], outline=c + (255,), width=4)
            if h.label:
                labels.append(((cx, cy - r - 14), h.label, c))
        elif h.kind == "dash":
            _dashed(dr, [P(*h.at), P(*h.dashed_to)], c + (255,), 4, on=12, off=7)
            if h.label:
                mx, my = P((h.at[0] + h.dashed_to[0]) / 2, (h.at[1] + h.dashed_to[1]) / 2)
                labels.append(((mx, my + 18), h.label, c))
    fb = _font(15, bold=True)
    placed: List[Tuple[float, float, float, float]] = []
    for (lx, ly), txt, c in labels:
        w = dr.textlength(txt, font=fb)
        lx = min(max(lx, w / 2 + 6), px_w - w / 2 - 6)
        # nudge a label up or down until it no longer covers one already placed
        for dy in (0, 30, -30, 60, -60, 90, -90):
            y = min(max(ly + dy, 14), px_h - 14)
            box = (lx - w / 2 - 8, y - 14, lx + w / 2 + 8, y + 14)
            if not any(box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3] for b in placed):
                break
        ly = y
        placed.append(box)
        dr.rounded_rectangle([lx - w / 2 - 6, ly - 12, lx + w / 2 + 6, ly + 12], radius=5,
                             fill=(255, 255, 255, 240), outline=c + (255,), width=2)
        dr.text((lx, ly), txt, font=fb, fill=c, anchor="mm")

    # --- scale bar, so a non-engineer can read sizes off the picture
    bar_m = 1 if (x1 - x0) < 9000 else 2
    blen = bar_m * 1000 * sc
    bx, by = 16, px_h - 18
    dr.rectangle([bx, by - 4, bx + blen, by], fill=(30, 30, 30, 255))
    dr.text((bx + blen + 8, by - 2), f"{bar_m} m", font=_font(13, bold=True), fill=(30, 30, 30), anchor="lm")
    dr.rectangle([0, 0, px_w - 1, px_h - 1], outline=(200, 200, 200, 255), width=1)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# =============================================================================
# Questions
# =============================================================================
_RX_DRAWN = re.compile(r"drawn width (\d+) but schedule says (\d+)")
_RX_LABEL = re.compile(r"plan label (\d+)x(\d+) but schedule says (\d+)x(\d+)")
_RX_DEFAULT = re.compile(r"no size on plan or schedule: U\.N\.O\. (\d+)x(\d+) applied")

SCHEDULE_WORDS = ["schedule", "beam schedule", "table", "as per schedule", "schedule is right", "schedule is correct"]
DRAWING_WORDS = ["drawing", "drawn", "as drawn", "the lines", "lines", "measured on the plan", "drawing is right"]
PLAN_LABEL_WORDS = ["plan label", "label", "written on the plan", "plan says", "plan", "the plan is right"]
KEEP_WORDS = ["keep", "keep it", "leave it", "as now", "as it is", "fine", "correct", "ok", "okay", "default", "right"]


def _set(el_id: str, field: str, value: float, list_name: str = "members") -> QuestionChange:
    return QuestionChange(element_id=el_id, list_name=list_name, field=field, value=round(value, 4))


def _beam_question(b, el, sheet: str) -> Optional[ReviewQuestion]:
    flags = " | ".join(b.flags)
    tag = el.tag
    D = _mm(el.depth_m)
    m_def, m_lab, m_drawn = _RX_DEFAULT.search(flags), _RX_LABEL.search(flags), _RX_DRAWN.search(flags)
    size_fields = [CustomField(field="width_m", label="Width", min_mm=75, max_mm=1500),
                   CustomField(field="depth_m", label="Depth", min_mm=100, max_mm=3000)]
    if m_def:
        wu, du = int(m_def.group(1)), int(m_def.group(2))
        opts = [QuestionOption(id="keep", label=f"Keep {wu} × {du} mm", current=True,
                               detail=f"{tag} stays {wu} × {du} mm, the drawing's general size.",
                               keywords=KEEP_WORDS + ["u.n.o", "uno", "unless noted"],
                               values_mm={"width_m": wu, "depth_m": du},
                               changes=[_set(el.id, "width_m", wu / 1000), _set(el.id, "depth_m", du / 1000)])]
        extra = ""
        if m_drawn:
            wd = int(m_drawn.group(1))
            extra = f" Its two edge lines are drawn {wd} mm apart."
            opts.append(QuestionOption(id="drawing", label=f"Use the drawn width: {wd} × {du} mm",
                                       detail=f"{tag} becomes {wd} × {du} mm.",
                                       keywords=DRAWING_WORDS, values_mm={"width_m": wd},
                                       changes=[_set(el.id, "width_m", wd / 1000)]))
        return ReviewQuestion(
            key=f"beam-default:{tag}", kind="element", topic="Beam size", title=f"{tag}: no size anywhere — is {wu} × {du} right?",
            question=(f"{tag} has no size written on the plan and no row in the beam schedule, so the system used the "
                      f"drawing's general note size (\"unless noted otherwise\"): {wu} × {du} mm.{extra} Is that right?"),
            why="The size sets this beam's concrete and shuttering. If you know the real size, type it.",
            element_ids=[el.id], element_tags=[tag], options=opts, source_sheet=sheet,
            custom=QuestionCustom(prompt="Or type the real size", fields=size_fields, element_ids=[el.id]))
    if m_lab:
        bp, dp, bs, ds = (int(m_lab.group(i)) for i in range(1, 5))
        return ReviewQuestion(
            key=f"beam-size:{tag}", kind="element", topic="Beam size",
            title=f"{tag}: {bs} × {ds} (schedule) or {bp} × {dp} (plan)?",
            question=(f"The size written next to {tag} on the plan is {bp} × {dp} mm, but the beam schedule — the table "
                      f"of all beams on the same sheet — says {bs} × {ds} mm. Which size should be measured?"),
            why=f"Today the system uses the schedule. The difference is {abs(dp - ds)} mm in depth"
                + (f" and {abs(bp - bs)} mm in width" if bp != bs else "") + f" over {el.length_m:.2f} m of beam.",
            element_ids=[el.id], element_tags=[tag], source_sheet=sheet,
            options=[
                QuestionOption(id="schedule", label=f"Use the schedule: {bs} × {ds} mm", current=True,
                               detail=f"{tag} stays {bs} × {ds} mm.", keywords=SCHEDULE_WORDS,
                               values_mm={"width_m": bs, "depth_m": ds},
                               changes=[_set(el.id, "width_m", bs / 1000), _set(el.id, "depth_m", ds / 1000)]),
                QuestionOption(id="plan", label=f"Use the plan label: {bp} × {dp} mm",
                               detail=f"{tag} becomes {bp} × {dp} mm.", keywords=PLAN_LABEL_WORDS,
                               values_mm={"width_m": bp, "depth_m": dp},
                               changes=[_set(el.id, "width_m", bp / 1000), _set(el.id, "depth_m", dp / 1000)]),
            ],
            custom=QuestionCustom(prompt="Or type the real size", fields=size_fields, element_ids=[el.id]))
    if m_drawn:
        wd, ws = int(m_drawn.group(1)), int(m_drawn.group(2))
        return ReviewQuestion(
            key=f"beam-width:{tag}", kind="element", topic="Beam width", title=f"{tag}: {ws} or {wd} mm wide?",
            question=(f"The beam schedule says {tag} is {ws} mm wide, but on the plan its two edge lines are drawn "
                      f"{wd} mm apart. Which width is right?"),
            why=f"Today the system uses the schedule ({ws} mm). Width changes this beam's concrete and its "
                f"bottom shuttering over {el.length_m:.2f} m.",
            element_ids=[el.id], element_tags=[tag], source_sheet=sheet,
            options=[
                QuestionOption(id="schedule", label=f"Use the schedule: {ws} mm", current=True,
                               detail=f"{tag} stays {ws} × {D} mm.", keywords=SCHEDULE_WORDS,
                               values_mm={"width_m": ws}, changes=[_set(el.id, "width_m", ws / 1000)]),
                QuestionOption(id="drawing", label=f"Use the drawing: {wd} mm",
                               detail=f"{tag} becomes {wd} × {D} mm.", keywords=DRAWING_WORDS,
                               values_mm={"width_m": wd}, changes=[_set(el.id, "width_m", wd / 1000)]),
            ],
            custom=QuestionCustom(prompt="Or type the right width", fields=[size_fields[0]], element_ids=[el.id]))
    return None


def _column_question(group: Sequence[Tuple[object, object, str]], sheet: str) -> ReviewQuestion:
    """One question for filled column shapes with no name that sit together (often a legend)."""
    c0 = group[0][0]
    cx, cy = (c0.bbox[0] + c0.bbox[2]) / 2, (c0.bbox[1] + c0.bbox[3]) / 2
    sizes = [f"{c.measured[0]} × {c.measured[1]} mm" for c, _, _ in group]
    many = len(group) > 1
    return ReviewQuestion(
        key=f"col-noname:{round(cx / 100)},{round(cy / 100)}", kind="element", topic="Column",
        title=(f"{len(group)} filled column shapes with no name — are they real columns?" if many
               else "A filled column shape with no name — is it a real column?"),
        question=((f"There are {len(group)} filled column shapes here ({', '.join(sizes)}) with no name (like C1 or W2) "
                   "next to them. Are they real columns that should be measured?") if many else
                  (f"There is a filled column shape here, {sizes[0]}, but no name (like C1 or W2) next to it. "
                   "Is it a real column that should be measured?")),
        why=("If real, their concrete and shuttering are counted. If they are a legend, a symbol or a leftover, they "
             "should go." if many else
             "If it is real, its concrete and shuttering are counted. If it is a legend, a symbol or a leftover, it should go."),
        element_ids=[el.id for _, el, _ in group], element_tags=[el.tag for _, el, _ in group], source_sheet=sheet,
        options=[
            QuestionOption(id="keep", label="Yes — keep " + ("them" if many else "it") + " as columns" * many + " as a column" * (not many),
                           current=True, detail="Measured as " + ", ".join(sizes) + (" columns." if many else " column."),
                           keywords=["yes", "keep", "keep it", "keep them", "it is real", "they are real", "real column",
                                     "it is a column", "correct"]),
            QuestionOption(id="remove", label="No — not " + ("columns" if many else "a column") + ", remove " + ("them" if many else "it"),
                           detail="Taken out of the measurement.",
                           keywords=["no", "remove", "delete", "not a column", "not columns", "isn't a column",
                                     "is not a column", "not real", "ignore", "drop", "symbol", "legend", "leftover",
                                     "take it out", "take them out"],
                           changes=[QuestionChange(element_id=el.id, list_name=ln, remove=True) for _, el, ln in group]),
        ])


# ------------------------------------------------------------------ rule: slab over beam
def _slab_over_beam(res: StructuralReadResult, ex: MeasurementExtraction, by_id: Dict[str, object],
                    sheet: str, cfg: StructuralConfig) -> Optional[Tuple[ReviewQuestion, bytes]]:
    slabs = [(s, Polygon(s.poly).buffer(0)) for s in res.slabs if s.found and len(s.poly) >= 3]
    rows = []      # (beam result, element, thickness_mm, touching slab results)
    for v in res.beams.values():
        for b in v:
            el = by_id.get(res.element_ids.get(f"beam:{b.uid}", ""))
            if el is None or len(b.geom) < 2:
                continue
            band = LineString(b.geom).buffer(b.width / 2 + 60, cap_style=2)
            touch = [(s, g) for s, g in slabs if band.intersects(g) and band.intersection(g).area > 20_000]
            if not touch:
                continue
            t = max((s.thickness_mm or cfg.default_slab_thickness_mm) for s, _ in touch)
            rows.append((b, el, t, touch))
    if not rows:
        return None
    groups: Dict[int, List[tuple]] = {}
    for r in rows:
        groups.setdefault(r[2], []).append(r)
    changes: List[QuestionChange] = []
    moved = 0.0
    fw = 0.0
    for b, el, t, _ in rows:
        changes.append(_set(el.id, "slab_thickness_m", t / 1000))
        moved += el.length_m * el.width_m * t / 1000
        fw += 2 * el.length_m * t / 1000
    level = rows[0][1].level
    for t, grp in sorted(groups.items()):
        sum_l = sum(el.length_m for _, el, _, _ in grp)
        sum_lb = sum(el.length_m * el.width_m for _, el, _, _ in grp)
        strip = SlabEl(id=new_id(), tag=f"Over beams ({t} mm)", length_m=round(sum_l, 3),
                       width_m=round(sum_lb / sum_l, 4), thickness_m=t / 1000, level=level, beam_width_m=0,
                       soffit_formwork=False, confidence=1.0, source_sheet=sheet,
                       evidence=["IS 1200: slab measured continuous over the beams",
                                 f"{len(grp)} beams under {t} mm slab, {sum_l:.2f} m long in total "
                                 f"(length = total beam length, width = average beam width)"])
        changes.append(QuestionChange(element_id=strip.id, list_name="slabs", add=strip.model_dump(mode="json")))
    # the picture: a long beam with slab on both sides
    def score(r):
        b, el, t, touch = r
        return (len({s.tag for s, _ in touch}) >= 2, el.length_m)
    b, el, t, touch = max(rows, key=score)
    hl = [Highlight("poly", GREEN, poly=list(g.exterior.coords), label=f"slab {s.tag} ({s.thickness_mm or cfg.default_slab_thickness_mm})")
          for s, g in touch[:3]]
    beam_hl = Highlight("beam", RED, geom=b.geom, width=b.width, label=f"{el.tag}: overlap {t} mm")
    png = render_crop(res, hl + [beam_hl], cfg, focus=[beam_hl])
    n = len(rows)
    q = ReviewQuestion(
        key="rule:slab-over-beam", kind="rule", topic="Measuring rule",
        title="Where the slab sits on a beam — does that concrete belong to the slab or the beam?",
        question=("The floor slab passes over the top of every beam. That overlap is one block of concrete and must be "
                  "counted once — either in the slab or in the beam. Today the system gives it to the beam (beams at full "
                  "depth, slabs measured only between the beams). Under IS 1200 the slab is measured continuous over the "
                  "beams and each beam only below the slab."),
        why=(f"The total concrete does not change. What changes: {moved:.2f} cum moves from the beam line to the slab "
             f"line, and beam side shuttering drops by {fw:.1f} sqm, because a beam's sides are only shuttered below "
             f"the slab. This affects {n} beams."),
        element_ids=[el.id for _, el, _, _ in rows], element_tags=[el.tag for _, el, _, _ in rows], source_sheet=sheet,
        options=[
            QuestionOption(id="beam", label="The beam keeps it (as now)", current=True,
                           detail="Beams at full depth; slabs only between the beams.",
                           keywords=["beam keeps", "beam keeps it", "full depth", "as now", "keep as is", "no change"]),
            QuestionOption(id="slab", label="The slab keeps it — IS 1200", recommended=True,
                           detail=(f"Slab measured over the beams; {n} beams measured below the slab. {moved:.2f} cum "
                                   f"moves to the slab line, total unchanged."),
                           keywords=["is 1200", "is1200", "is-1200", "is code", "slab keeps", "slab keeps it", "slab",
                                     "over the beam", "over the beams", "continuous", "below the slab", "under the slab",
                                     "rulebook", "standard", "code"],
                           changes=changes),
        ])
    return q, png


# ------------------------------------------------------------------ rule: corners
def _corners(res: StructuralReadResult, by_id: Dict[str, object], sheet: str,
             cfg: StructuralConfig) -> Optional[Tuple[ReviewQuestion, bytes]]:
    beams = {b.uid: b for v in res.beams.values() for b in v}

    def regular(name: str) -> bool:
        return name.startswith("B") and not name.startswith(("BKT", "HB"))

    events = []
    for b in beams.values():
        for j in b.junctions:
            o = beams.get(j["other"])
            if j["kind"] != "corner" or o is None or not (regular(b.name) and regular(o.name)):
                continue
            if j["inside"] < 100 or j["other_inside"] <= 0:
                continue
            x = by_id.get(res.element_ids.get(f"beam:{b.uid}", ""))
            y = by_id.get(res.element_ids.get(f"beam:{o.uid}", ""))
            if x is not None and y is not None:
                events.append((b, o, x, y, j))
    if not events:
        return None
    changes: List[QuestionChange] = []
    pairs = []
    for b, o, x, y, j in events:
        changes.append(QuestionChange(element_id=x.id, field="length_m", delta=round(j["inside"] / 1000, 4)))
        changes.append(QuestionChange(element_id=y.id, field="length_m", delta=round(-j["other_inside"] / 1000, 4)))
        pairs.append(f"{x.tag}/{y.tag}")
    b, o, x, y, j = max(events, key=lambda e: e[4]["inside"])
    cx, cy = j["at"]
    blk = Point(cx, cy).buffer(max(b.width, o.width) / 2, cap_style=3)
    hl = [Highlight("beam", AMBER, geom=b.geom, width=b.width, label=f"{x.tag} (longer, stops)"),
          Highlight("beam", BLUE, geom=o.geom, width=o.width, label=f"{y.tag} (shorter, runs through)"),
          Highlight("poly", RED, poly=list(blk.exterior.coords), label="corner block")]
    png = render_crop(res, hl, cfg, focus=[hl[2]])
    q = ReviewQuestion(
        key="rule:corner", kind="rule", topic="Measuring rule",
        title="Where two beams meet at a corner, which one owns the corner block?",
        question=(f"At {len(events)} corner{'s' if len(events) != 1 else ''} two beams meet at a right angle: "
                  f"{_join(pairs)}. The square of concrete where they overlap must be counted in exactly one of them. "
                  "Today the shorter beam runs through the corner and the longer one stops at its side."),
        why="The total concrete is the same either way; this decides which beam's length the corner adds to, which "
            "is how the contractor's sheet will list it.",
        element_ids=list(dict.fromkeys([e[2].id for e in events] + [e[3].id for e in events])),
        element_tags=list(dict.fromkeys([e[2].tag for e in events] + [e[3].tag for e in events])), source_sheet=sheet,
        options=[
            QuestionOption(id="shorter", label="The shorter beam runs through (as now)", current=True,
                           detail="Longer beams stop at the side of the shorter one.",
                           keywords=["shorter", "short one", "shorter beam", "as now", "keep as is", "no change"]),
            QuestionOption(id="longer", label="The longer beam runs through",
                           detail="Each longer beam gets the corner; each shorter one stops at its side.",
                           keywords=["longer", "long one", "longer beam", "main beam", "bigger beam"],
                           changes=changes),
        ])
    return q, png


# ------------------------------------------------------------------ rule: pardi
def _pardi(res: StructuralReadResult, by_id: Dict[str, object], sheet: str,
           cfg: StructuralConfig) -> Optional[Tuple[ReviewQuestion, bytes]]:
    """A pardi (a low concrete wall) that continues the line between two beams: both beams
    stop where it starts. Only the two-sided pattern counts — a label next to one beam end
    is too uncertain to drive a rule."""
    labels = [t for t in res.plan_texts if re.search(r"\bPARDI\b", t.text.upper()) and "CUTOUT" not in t.text.upper()]
    found = []        # (label, [(beam, element, end point)])
    for t in labels:
        sides: Dict[int, Tuple[float, object, object, tuple]] = {}
        for v in res.beams.values():
            for b in v:
                g = b.geom
                el = by_id.get(res.element_ids.get(f"beam:{b.uid}", ""))
                if el is None or len(g) < 2:
                    continue
                d = math.degrees(math.atan2(g[-1][1] - g[0][1], g[-1][0] - g[0][0])) % 180
                dd = abs(d - t.rot % 180) % 180
                if min(dd, 180 - dd) > 15:
                    continue
                for end, prev in ((g[0], g[1]), (g[-1], g[-2])):
                    ox, oy = end[0] - prev[0], end[1] - prev[1]
                    L = math.hypot(ox, oy) or 1
                    ox, oy = ox / L, oy / L
                    dx, dy = t.cx - end[0], t.cy - end[1]
                    along, lat = dx * ox + dy * oy, abs(-dx * oy + dy * ox)
                    if 0 < along < 3500 and lat < 900:
                        # which side of the label is this end on (along the label's direction)?
                        th = math.radians(t.rot)
                        side = 1 if (end[0] - t.cx) * math.cos(th) + (end[1] - t.cy) * math.sin(th) > 0 else -1
                        cost = along + 2 * lat
                        if side not in sides or cost < sides[side][0]:
                            sides[side] = (cost, b, el, end)
        if len(sides) == 2 and sides[1][2].id != sides[-1][2].id:
            found.append((t, [sides[-1][1:], sides[1][1:]]))
    if not found:
        return None
    els, pairs = [], []
    for t, two in found:
        for b, el, end in two:
            if el.id not in [e.id for e in els]:
                els.append(el)
        pairs.append(f"{two[0][1].tag} and {two[1][1].tag}")
    thk = re.search(r"(\d{2,3})\s*(?:MM|X)", found[0][0].text.upper())
    thk_txt = f"{thk.group(1)} mm thick" if thk else "thin"
    t, two = found[0]
    (b1, e1, p1), (b2, e2, p2) = two
    hl = [Highlight("beam", AMBER, geom=b1.geom, width=b1.width, label=e1.tag),
          Highlight("beam", AMBER, geom=b2.geom, width=b2.width, label=e2.tag),
          Highlight("dash", RED, at=p1, dashed_to=p2, label="pardi continues here"),
          Highlight("circle", RED, at=(t.cx, t.cy), radius=max(600, len(t.text) * t.h * 0.45), label="")]
    png = render_crop(res, hl, cfg)
    q = ReviewQuestion(
        key="rule:pardi", kind="rule", topic="Measuring rule",
        title="Beams that end where a pardi wall continues — where should they stop?",
        question=(f"{_join([e.tag for e in els])} each end where a pardi — a low concrete wall, here {thk_txt} — continues the same line "
                  f"(circled). Today the system measures each beam up to where the pardi starts. Should they be measured "
                  f"shorter at the pardi end, and if so by how much?"),
        why=f"This changes the length of {len(els)} beams: {_join([e.tag for e in els])}.",
        element_ids=[e.id for e in els], element_tags=[e.tag for e in els], source_sheet=sheet,
        options=[QuestionOption(id="keep", label="Up to where the pardi starts (as now)", current=True,
                                detail="No change.",
                                keywords=["as now", "keep", "keep as is", "no change", "where the pardi starts",
                                          "up to the pardi", "fine", "correct", "leave it"])],
        custom=QuestionCustom(prompt="Or say how much shorter each one should be",
                              fields=[CustomField(field="length_m", label="Shorten each by", min_mm=10, max_mm=1500)],
                              mode="shorten", element_ids=[e.id for e in els]))
    return q, png


# ------------------------------------------------------------------ all of it
def build_questions(res: StructuralReadResult, ex: MeasurementExtraction, sheet: str,
                    cfg: StructuralConfig = DEFAULT_CONFIG) -> List[Tuple[ReviewQuestion, Optional[bytes]]]:
    by_id: Dict[str, object] = {e.id: e for e in list(ex.members) + list(ex.walls) + list(ex.slabs)}
    out: List[Tuple[ReviewQuestion, Optional[bytes]]] = []
    for v in res.beams.values():
        for b in v:
            if not b.flags:
                continue
            el = by_id.get(res.element_ids.get(f"beam:{b.uid}", ""))
            if el is None:
                continue
            q = _beam_question(b, el, sheet)
            if q is None:
                continue
            hl = Highlight("beam", AMBER, geom=b.geom, width=b.width, label=el.tag)
            out.append((q, render_crop(res, [hl], cfg) if len(b.geom) >= 2 else None))
    wall_ids = {w.id for w in ex.walls}
    groups: List[List[Tuple[object, object, str]]] = []      # unnamed shapes that sit together
    for ci, c in enumerate(res.columns):
        if c.name:
            continue
        el = by_id.get(res.element_ids.get(f"col:{ci}", ""))
        if el is None:
            continue
        item = (c, el, "walls" if el.id in wall_ids else "members")
        ctr = ((c.bbox[0] + c.bbox[2]) / 2, (c.bbox[1] + c.bbox[3]) / 2)
        for g in groups:
            if any(math.dist(ctr, ((o.bbox[0] + o.bbox[2]) / 2, (o.bbox[1] + o.bbox[3]) / 2)) < 2000 for o, _, _ in g):
                g.append(item)
                break
        else:
            groups.append([item])
    for g in groups:
        g.sort(key=lambda t: -(t[0].bbox[1] + t[0].bbox[3]))
        hl = [Highlight("rect", RED, bbox=[c.bbox[0] - 120, c.bbox[1] - 120, c.bbox[2] + 120, c.bbox[3] + 120],
                        label="no name" if i == 0 else "") for i, (c, _, _) in enumerate(g)]
        out.append((_column_question(g, sheet), render_crop(res, hl, cfg)))
    for fn in (_slab_over_beam, _corners, _pardi):
        try:
            r = fn(res, ex, by_id, sheet, cfg) if fn is _slab_over_beam else fn(res, by_id, sheet, cfg)
        except Exception:  # noqa: BLE001 - a rule we cannot work out is simply not asked
            r = None
        if r:
            out.append(r)
    # rule questions first: one answer each fixes many beams
    out.sort(key=lambda qp: 0 if qp[0].kind == "rule" else 1)
    return out
