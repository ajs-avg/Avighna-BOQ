"""Answering review questions: understand a typed answer, apply a confirmed one, undo it.

Safety model, in order:
1. Every question carries its options as exact element edits (built by the reader).
2. A typed answer is only *interpreted*: Gemini (or, without a key, a keyword/number
   matcher) maps it to one option or to typed numbers. The sentence shown back to the
   person is generated here from that structured choice, never from AI prose.
3. Nothing changes until the person confirms. The decision keeps who, when, the exact
   words, and every value it changed, so it can be undone, and it is re-applied by
   question key when the drawing is re-read.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from app.models.schemas import (AnswerRequest, AppliedChange, Decision, Interpretation, JobRecord, MemberEl,
                                QuestionChange, ReviewQuestion, SlabEl, WallEl)

log = logging.getLogger(__name__)

_LIST_MODEL = {"members": MemberEl, "walls": WallEl, "slabs": SlabEl}
_FIELD_WORDS = {"width_m": "width", "depth_m": "depth", "length_m": "length", "thickness_m": "thickness",
                "slab_thickness_m": "slab thickness", "height_m": "height"}
_MIN = {"width_m": 0.05, "depth_m": 0.05, "length_m": 0.05, "thickness_m": 0.05, "height_m": 0.1,
        "slab_thickness_m": 0.0}


class QuestionError(ValueError):
    pass


# ============================================================================ describe
def _join(tags: List[str]) -> str:
    tags = list(dict.fromkeys(tags))
    if len(tags) <= 1:
        return "".join(tags)
    if len(tags) > 6:
        return ", ".join(tags[:5]) + f" and {len(tags) - 5} more"
    return ", ".join(tags[:-1]) + " and " + tags[-1]


def _fmt(v: float) -> str:
    return f"{v:g}"


def describe(q: ReviewQuestion, option_id: Optional[str], values: Dict[str, float]) -> str:
    """The sentence the person confirms. Built from the structured choice only."""
    if option_id:
        o = next((o for o in q.options if o.id == option_id), None)
        if o is None:
            raise QuestionError(f"Unknown option '{option_id}'")
        return f"{o.label}. {o.detail}".strip()
    if not q.custom or not values:
        raise QuestionError("Nothing to apply: pick an option or type a number")
    tags = _join(q.element_tags)
    if q.custom.mode == "shorten":
        v = values.get("length_m")
        if v is None:
            raise QuestionError("Say how many millimetres shorter")
        return f"Shorten {tags} by {_fmt(v)} mm each."
    fields = [f for f in q.custom.fields if f.field in values]
    if len(fields) >= 2:
        names = " × ".join(_FIELD_WORDS[f.field] for f in fields)
        return f"Set {tags} to {' × '.join(_fmt(values[f.field]) for f in fields)} mm ({names})."
    f = fields[0]
    return f"Set the {_FIELD_WORDS[f.field]} of {tags} to {_fmt(values[f.field])} mm."


def _validate_values(q: ReviewQuestion, values: Dict[str, float]) -> Dict[str, float]:
    if not values:
        return {}
    if not q.custom:
        raise QuestionError("This question only takes one of its options")
    allowed = {f.field: f for f in q.custom.fields}
    out = {}
    for k, v in values.items():
        f = allowed.get(k)
        if f is None:
            raise QuestionError(f"'{k}' cannot be set on this question")
        if not (f.min_mm <= float(v) <= f.max_mm):
            raise QuestionError(f"{f.label} must be between {f.min_mm:g} and {f.max_mm:g} mm")
        out[k] = float(v)
    return out


# ============================================================================ interpret
_NUM_RX = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(mm|millimet(?:er|re)s?|cm|m(?:et(?:er|re)s?)?)?(?![\w])", re.I)
_SIZE_RX = re.compile(r"(\d{2,4}(?:\.\d+)?)\s*(?:x|×|\*|by)\s*(\d{2,4}(?:\.\d+)?)", re.I)
_NEG_RX = re.compile(r"\b(not|don'?t|do not|never|isn'?t|is not|no need|instead of|rather than)\b[\w\s,'-]{0,18}$", re.I)


_STANDARD_RX = re.compile(r"\bis\s*[-:]?\s*\d{3,5}\b", re.I)     # "IS 1200" is a rulebook, not a size
_FIELD_SYNONYMS = {"width_m": ("width", "wide"), "depth_m": ("depth", "deep"), "length_m": ("length", "long", "shorter"),
                   "thickness_m": ("thick",), "height_m": ("height", "high", "tall"), "slab_thickness_m": ("slab",)}


def _numbers_mm(text: str) -> List[float]:
    out = []
    text = _STANDARD_RX.sub(" ", text)
    for m in _NUM_RX.finditer(text):
        v = float(m.group(1))
        u = (m.group(2) or "").lower()
        if u.startswith("cm"):
            v *= 10
        elif u.startswith("m") and not u.startswith("mm") and not u.startswith("mil"):
            v *= 1000
        out.append(round(v, 1))
    return out


def _keyword_scores(q: ReviewQuestion, t: str) -> Tuple[Dict[str, float], Dict[str, bool]]:
    scores, negated = {}, {}
    for o in q.options:
        sc, neg = 0.0, False
        for kw in o.keywords:
            for m in re.finditer(r"(?<![a-z0-9])" + re.escape(kw.lower()) + r"(?![a-z0-9])", t):
                if _NEG_RX.search(t[:m.start()]):
                    neg = True
                    sc -= len(kw)
                else:
                    sc += len(kw)
                break
        scores[o.id], negated[o.id] = sc, neg
    return scores, negated


def interpret_rules(q: ReviewQuestion, text: str) -> Interpretation:
    """Deterministic reading of a typed answer: option keywords, then the numbers."""
    t = " " + re.sub(r"\s+", " ", text.lower()).strip() + " "
    scores, negated = _keyword_scores(q, t)
    # numbers: a size "200 x 600", or loose numbers
    values: Dict[str, float] = {}
    m = _SIZE_RX.search(_STANDARD_RX.sub(" ", t))
    nums = _numbers_mm(t)
    custom_fields = [f.field for f in q.custom.fields] if q.custom else []
    by_number: Optional[str] = None
    if m and len(custom_fields) >= 2:
        w, d = float(m.group(1)), float(m.group(2))
        for o in q.options:
            if o.values_mm.get(custom_fields[0]) == w and o.values_mm.get(custom_fields[1]) == d:
                by_number = o.id
        if by_number is None:
            values = {custom_fields[0]: w, custom_fields[1]: d}
    elif nums:
        hits = {o.id for o in q.options for n in nums if n in o.values_mm.values()}
        if len(hits) == 1:
            by_number = hits.pop()
        elif not hits and q.custom:
            n = nums[0]
            if q.custom.mode == "shorten":
                values = {"length_m": n}
            elif len(custom_fields) == 1:
                values = {custom_fields[0]: n}
            else:   # one number for a two-field size: which one? use the field named in the text
                named = [f for f in custom_fields if any(w in t for w in _FIELD_SYNONYMS.get(f, ()))]
                if len(named) == 1:
                    values = {named[0]: n}
    best = max(scores.values()) if scores else 0
    top = [k for k, v in scores.items() if v == best and v > 0]
    by_word = top[0] if len(top) == 1 else None
    # "not the schedule" with two options means the other one
    if by_word is None and len(q.options) == 2 and sum(negated.values()) == 1 and best <= 0:
        by_word = next(k for k, v in negated.items() if not v)

    def ok(option_id=None, vals=None) -> Interpretation:
        vals = vals or {}
        try:
            vals = _validate_values(q, vals)
            return Interpretation(understood=True, option_id=option_id, custom_values=vals,
                                  understood_as=describe(q, option_id, vals), via="rules")
        except QuestionError as exc:
            return Interpretation(understood=False, message=str(exc), via="rules")

    if values and not by_number:     # a typed number that matches no option wins over words
        return ok(vals=values)
    if by_number and (by_word in (None, by_number)):
        return ok(option_id=by_number)
    if by_word and not by_number:
        return ok(option_id=by_word)
    examples = " or ".join(f"\"{o.label.split(':')[0].split(' (')[0]}\"" for o in q.options[:2])
    return Interpretation(
        understood=False, via="rules",
        message=("I couldn't tell which answer you mean. Press one of the buttons, or say it another way — e.g. "
                 + examples + (", or type a number in mm." if q.custom else ".")))


class _AIValue(BaseModel):
    field: str
    mm: float


class _AIAnswer(BaseModel):
    understood: bool
    option_id: str = Field("", description="One of the allowed option ids, or empty")
    values: List[_AIValue] = Field(default_factory=list)
    message: str = Field("", description="If not understood: one short sentence saying what is unclear")


def _ai_prompt(q: ReviewQuestion, text: str) -> str:
    opts = "\n".join(f"- id={o.id}: {o.label}. {o.detail}" for o in q.options)
    custom = ""
    if q.custom:
        fl = ", ".join(f"{f.field} ({f.label}, {f.min_mm:g}-{f.max_mm:g} mm)" for f in q.custom.fields)
        custom = (f"\nInstead of an option the reviewer may give numbers in millimetres for: {fl}."
                  + (" These numbers are how much SHORTER each beam gets." if q.custom.mode == "shorten" else ""))
    return (
        "A construction reviewer is answering a question about a structural drawing. Map their typed answer onto "
        "exactly one allowed choice. Do not decide anything yourself: if the answer is unclear, contradictory, or "
        "about something else, return understood=false with one short plain-English sentence in message.\n\n"
        f"Question: {q.title}\n{q.question}\n\nAllowed options:\n{opts}{custom}\n\n"
        f"Reviewer's answer: \"{text}\"\n\n"
        "Return option_id (one of the ids above) OR values (field + mm), never both. Convert metres or cm to mm.")


def interpret(q: ReviewQuestion, text: str, ai=None) -> Interpretation:
    """AI first when it is on; the keyword/number matcher otherwise (or if the AI fails)."""
    if ai is not None and getattr(ai, "enabled", False):
        try:
            res = ai.generate_json(_AIAnswer, _ai_prompt(q, text), tier="fast", temperature=0.0,
                                   max_output_tokens=1024)
            if not res.understood:
                return Interpretation(understood=False, message=res.message or "I couldn't tell which answer you mean.",
                                      via="ai")
            vals = {v.field: v.mm for v in res.values}
            opt = res.option_id or None
            if opt and opt not in {o.id for o in q.options}:
                raise QuestionError("AI picked an unknown option")
            if opt and vals:
                vals = {}
            vals = _validate_values(q, vals)
            return Interpretation(understood=True, option_id=opt, custom_values=vals,
                                  understood_as=describe(q, opt, vals), via="ai")
        except QuestionError as exc:
            return Interpretation(understood=False, message=str(exc), via="ai")
        except Exception as exc:  # noqa: BLE001 - AI down: the matcher still works
            log.info("AI interpretation failed, keyword matcher used: %s", exc)
    return interpret_rules(q, text)


# ============================================================================ apply / undo
def _find(job: JobRecord, list_name: str, element_id: str):
    lst = getattr(job.elements, list_name)
    for i, e in enumerate(lst):
        if e.id == element_id:
            return i, e
    return -1, None


def _changes_for(q: ReviewQuestion, option_id: Optional[str], values: Dict[str, float]) -> List[QuestionChange]:
    if option_id:
        o = next((o for o in q.options if o.id == option_id), None)
        if o is None:
            raise QuestionError(f"Unknown option '{option_id}'")
        return list(o.changes)
    if not q.custom:
        raise QuestionError("Pick one of the options")
    out = []
    for eid in q.custom.element_ids:
        if q.custom.mode == "shorten":
            out.append(QuestionChange(element_id=eid, list_name=q.custom.list_name, field="length_m",
                                      delta=-values["length_m"] / 1000))
        else:
            for f, v in values.items():
                out.append(QuestionChange(element_id=eid, list_name=q.custom.list_name, field=f, value=v / 1000))
    return out


def apply_answer(job: JobRecord, q: ReviewQuestion, req: AnswerRequest, by: str) -> Decision:
    if job.elements is None:
        raise QuestionError("This job has no elements")
    if q.status != "open":
        raise QuestionError("This question is already answered; undo it first to change the answer")
    values = _validate_values(q, req.custom_values)
    if not req.option_id and not values:
        raise QuestionError("Pick an option or type a number")
    understood = describe(q, req.option_id, values)
    changes = _changes_for(q, req.option_id, values)
    applied: List[AppliedChange] = []
    stamp = f"{datetime.utcnow():%d-%b-%Y %H:%M} UTC"
    for ch in changes:
        if ch.add is not None:
            el = _LIST_MODEL[ch.list_name].model_validate(ch.add)
            el.evidence = list(el.evidence) + [f"added by decision: {understood} ({by}, {stamp})"]
            getattr(job.elements, ch.list_name).append(el)
            applied.append(AppliedChange(element_id=el.id, list_name=ch.list_name, tag=getattr(el, "tag", ""), added=True))
            continue
        i, el = _find(job, ch.list_name, ch.element_id)
        if el is None:
            continue   # edited away by hand since the question was asked
        if ch.remove:
            applied.append(AppliedChange(element_id=el.id, list_name=ch.list_name, tag=el.tag,
                                         removed=el.model_dump(mode="json")))
            del getattr(job.elements, ch.list_name)[i]
            continue
        before = float(getattr(el, ch.field))
        after = before + ch.delta if ch.delta is not None else float(ch.value)
        after = round(max(after, _MIN.get(ch.field, 0.0)), 4)
        setattr(el, ch.field, after)
        el.evidence = [e for e in el.evidence if not e.startswith("decided:")] + [f"decided: {understood} ({by}, {stamp})"]
        applied.append(AppliedChange(element_id=el.id, list_name=ch.list_name, tag=el.tag, field=ch.field,
                                     before=before, after=after))
    # the element questions are settled: their flags go, confidence is a person's now
    if q.kind == "element":
        for eid in q.element_ids:
            for ln in ("members", "walls", "slabs"):
                _, el = _find(job, ln, eid)
                if el is not None:
                    applied.append(AppliedChange(element_id=el.id, list_name=ln, tag=el.tag,
                                                 flags_before=list(el.flags), confidence_before=el.confidence))
                    el.flags, el.confidence = [], 1.0
                    if not any(e.startswith("decided:") for e in el.evidence):
                        el.evidence = list(el.evidence) + [f"decided: {understood} ({by}, {stamp})"]
    d = Decision(question_id=q.id, question_key=q.key, option_id=req.option_id, custom_values=values,
                 answer_text=(req.answer_text or understood).strip()[:2000], understood_as=understood,
                 interpreted_by=req.interpreted_by, applied=applied, decided_by=by)
    job.decisions.append(d)
    q.status, q.decision_id = "answered", d.id
    return d


def undo_decision(job: JobRecord, d: Decision, by: str) -> None:
    if d.undone:
        raise QuestionError("Already undone")
    for a in reversed(d.applied):
        if a.added:
            lst = getattr(job.elements, a.list_name)
            setattr(job.elements, a.list_name, [e for e in lst if e.id != a.element_id])
        elif a.removed is not None:
            getattr(job.elements, a.list_name).append(_LIST_MODEL[a.list_name].model_validate(a.removed))
        else:
            _, el = _find(job, a.list_name, a.element_id)
            if el is None:
                continue
            if a.field is not None and a.before is not None:
                setattr(el, a.field, a.before)
            if a.flags_before is not None:
                el.flags = list(a.flags_before)
            if a.confidence_before is not None:
                el.confidence = a.confidence_before
            el.evidence = [e for e in el.evidence if not e.startswith("decided:")]
    d.undone, d.undone_by, d.undone_at = True, by, datetime.utcnow()
    for q in job.questions:
        if q.decision_id == d.id:
            q.status, q.decision_id = "open", None


def reapply_decisions(job: JobRecord) -> List[str]:
    """After the drawing is re-read: the latest confirmed answer for each question key is
    applied again to the fresh elements. Returns one line per re-applied answer."""
    latest: Dict[str, Decision] = {}
    for d in job.decisions:
        if not d.undone:
            latest[d.question_key] = d
    notes = []
    for key, d in latest.items():
        q = next((x for x in job.questions if x.key == key and x.status == "open"), None)
        if q is None:
            continue
        try:
            nd = apply_answer(job, q, AnswerRequest(option_id=d.option_id, custom_values=d.custom_values,
                                                     answer_text=d.answer_text, understood_as=d.understood_as,
                                                     interpreted_by=d.interpreted_by), d.decided_by)
        except QuestionError as exc:
            notes.append(f"Could not re-apply '{d.understood_as}': {exc}")
            continue
        # keep one record per answer: the new one replaces the old
        nd.id, nd.decided_at = d.id, d.decided_at
        q.decision_id = d.id
        job.decisions = [x for x in job.decisions if x is not d]
        notes.append(f"Re-applied earlier answer by {d.decided_by}: {d.understood_as}")
    return notes


def resolve_edited_questions(job: JobRecord) -> None:
    """After a hand edit on the Elements tab: an open element question whose element is gone,
    or whose flags were cleared by the edit, is settled by that edit."""
    if job.elements is None:
        return
    els = {e.id: e for e in list(job.elements.members) + list(job.elements.walls) + list(job.elements.slabs)}
    for q in job.questions:
        if q.status != "open" or q.kind != "element":
            continue
        if any(eid not in els or not els[eid].flags for eid in q.element_ids):
            q.status = "resolved_by_edit"
