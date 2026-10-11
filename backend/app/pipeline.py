"""Job pipeline: files -> converted -> sheets (inventory + preview + classification)
-> extraction (AI or heuristic) -> quantification (deterministic engines) -> ready."""
from __future__ import annotations

import logging
import shutil
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app import db, repository as repo
from app.ai.gemini import GeminiClient, GeminiUnavailable
from app.storage import get_storage
from app.ai.mappers import (
    classification_from_ai, fitout_from_ai, merge_fitout, merge_structural, structural_from_ai,
)
from app.ai.prompts import (
    SYSTEM, AIFitoutExtraction, AISheetClass, AIStructuralExtraction, classify_prompt, fitout_prompt,
    structural_prompt,
)
from app.config import get_settings
from app.engine.bbs import compute_bbs
from app.engine.boq import compute_boq
from app.extract.detect import detect_format
from app.extract.dwg_convert import ConversionError, convert_dwg_to_dxf
from app.extract.dxf_reader import load_dxf, paperspace_hints, read_dxf, render_layout_png
from app.extract.fitout_geometry import MeasuredFacts, measure_dxf, measure_from_inventory
from app.extract.heuristics import classify_sheet_heuristic, fitout_items_from_facts, structural_members_heuristic
from app.extract.image_reader import read_image, render_image_png
from app.extract.inventory import SheetInventory
from app.extract.pdf_reader import read_pdf, render_page_png, title_block_hints
from app.extract.tables import reconstruct_tables, tables_to_prompt
from app.models.schemas import (
    FitoutExtraction, JobEvent, JobRecord, JobStatus, Module, SheetRecord, StructuralExtraction, new_id,
)

log = logging.getLogger(__name__)


class _Sheet:
    """Working object for one sheet while the job runs."""

    def __init__(self, record: SheetRecord, inv: SheetInventory, kind: str, path: Path):
        self.record = record
        self.inv = inv
        self.kind = kind          # pdf | dxf | image
        self.path = path          # file to render / measure from
        self.hi_png: Optional[bytes] = None
        self.facts: Optional[MeasuredFacts] = None
        self.hints: List[str] = []   # paperspace / title-block strings (DXF)

    def title_hints(self) -> List[str]:
        return (self.hints + title_block_hints(self.inv))[:200]

    @property
    def label(self) -> str:
        r = self.record
        return f"{r.file_name} [{r.layout}]" if self.kind == "dxf" else f"{r.file_name} p{r.page_no}"


class Pipeline:
    _instance: Optional["Pipeline"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.executor = ThreadPoolExecutor(max_workers=max(1, get_settings().worker_threads), thread_name_prefix="job")

    @classmethod
    def get(cls) -> "Pipeline":
        with cls._lock:
            if cls._instance is None:
                cls._instance = Pipeline()
            return cls._instance

    def submit(self, job_id: str) -> None:
        self.executor.submit(self.run, job_id)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _event(job: JobRecord, status: JobStatus, message: str, progress: int) -> None:
        job.status = status
        job.progress = max(job.progress if status == job.status else 0, progress)
        job.events.append(JobEvent(at=datetime.utcnow(), status=status, message=message, progress=progress))
        repo.save_job(job)
        log.info("job %s: %s (%d%%) %s", job.id, status.value, progress, message)

    # ------------------------------------------------------------------ main
    def run(self, job_id: str) -> None:
        job = repo.get_job(job_id)
        if job is None:
            return
        s = get_settings()
        work = s.data_dir / "work" / job.id
        previews = s.data_dir / "previews" / job.id
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True, exist_ok=True)
        previews.mkdir(parents=True, exist_ok=True)
        ai = GeminiClient.get()
        try:
            job.error = None
            job.events = [e for e in job.events if e.status != JobStatus.failed] if job.events else []
            self._event(job, JobStatus.converting, "Detecting file formats and converting DWG files", 3)
            sources = self._convert(job, work)

            self._event(job, JobStatus.analysing, "Reading sheets, rendering previews", 15)
            sheets = self._read_sheets(job, sources, previews)
            job.sheet_count = len(sheets)
            repo.save_sheets(job.id, [sh.record for sh in sheets])
            self._event(job, JobStatus.analysing, f"{len(sheets)} sheet(s) read; classifying", 25)
            self._classify(job, sheets, ai)
            repo.save_sheets(job.id, [sh.record for sh in sheets])

            self._event(job, JobStatus.extracting, "Reading members / items from relevant sheets", 45)
            if job.module == Module.structural:
                self._extract_structural(job, sheets, ai)
            else:
                self._extract_fitout(job, sheets, sources, ai)
            repo.save_sheets(job.id, [sh.record for sh in sheets])

            self._event(job, JobStatus.quantifying, "Running the measurement engine", 88)
            recalculate(job)
            job.progress = 100
            self._event(job, JobStatus.ready, self._ready_message(job), 100)
            db.audit("job.ready", job.created_by_email, job.id, self._ready_message(job))
        except Exception as exc:  # noqa: BLE001
            log.error("job %s failed: %s\n%s", job.id, exc, traceback.format_exc())
            job.error = f"{type(exc).__name__}: {exc}"
            self._event(job, JobStatus.failed, job.error, job.progress)
            db.audit("job.failed", job.created_by_email, job.id, job.error)

    @staticmethod
    def _ready_message(job: JobRecord) -> str:
        if job.module == Module.structural and job.result:
            return f"{len(job.members)} members, {job.result.summary.grand_total_t:,.3f} t of steel"
        if job.boq:
            q = job.boq.summary.qty_by_unit
            return f"{job.boq.summary.line_count} BOQ lines ({q.get('m2', 0):,.0f} m², {q.get('lm', 0):,.0f} lm, {q.get('nos', 0):,.0f} nos)"
        return "Ready"

    # ------------------------------------------------------------------ stage 1: convert
    def _convert(self, job: JobRecord, work: Path) -> List[Tuple[str, str, Path]]:
        """Returns [(file_name, kind, path)] with kind in pdf | dxf | image."""
        out: List[Tuple[str, str, Path]] = []
        failures: List[str] = []
        n = len(job.source_files)
        for i, sf in enumerate(job.source_files):
            src = get_storage().resolve(sf.storage_path)
            if src is None:
                failures.append(f"{sf.name}: file missing in storage")
                continue
            fmt, mime, detail = detect_format(src)
            sf.format, sf.mime = fmt, mime
            if fmt == "dwg":
                try:
                    dxf = convert_dwg_to_dxf(src, work / "dxf")
                    out.append((sf.name, "dxf", dxf))
                except ConversionError as exc:
                    failures.append(f"{sf.name}: {exc}")
                    log.warning("DWG conversion failed for %s: %s", sf.name, exc)
            elif fmt == "dxf":
                out.append((sf.name, "dxf", src))
            elif fmt == "pdf":
                out.append((sf.name, "pdf", src))
            elif fmt == "image":
                out.append((sf.name, "image", src))
            else:
                failures.append(f"{sf.name}: unsupported format")
            self._event(job, JobStatus.converting, f"Converted {i + 1}/{n}: {sf.name} ({fmt} {detail})".strip(),
                        3 + int(10 * (i + 1) / max(n, 1)))
        if failures:
            job.events.append(JobEvent(at=datetime.utcnow(), status=JobStatus.converting,
                                       message="Skipped: " + " | ".join(failures)[:900], progress=job.progress))
        if not out:
            raise RuntimeError("No readable drawing files. " + " | ".join(failures))
        return out

    # ------------------------------------------------------------------ stage 2: read + preview
    def _read_sheets(self, job: JobRecord, sources: List[Tuple[str, str, Path]], previews: Path) -> List[_Sheet]:
        s = get_settings()
        sheets: List[_Sheet] = []
        for name, kind, path in sources:
            try:
                if kind == "pdf":
                    invs = read_pdf(path, max_pages=s.max_pages)
                    try:
                        import fitz
                        with fitz.open(str(path)) as _d:
                            if _d.page_count > s.max_pages:
                                job.events.append(JobEvent(at=datetime.utcnow(), status=JobStatus.analysing,
                                                           message=f"{name}: only the first {s.max_pages} of {_d.page_count} pages were read (MAX_PAGES)",
                                                           progress=job.progress))
                    except Exception:
                        pass
                elif kind == "dxf":
                    all_invs = read_dxf(path)
                    model = [inv for inv in all_invs if inv.layout == "Model"]
                    invs = model if (model and (model[0].texts or model[0].entity_counts)) else [inv for inv in all_invs if inv.texts]
                else:
                    invs = read_image(path)
            except Exception as exc:  # noqa: BLE001
                job.events.append(JobEvent(at=datetime.utcnow(), status=JobStatus.analysing,
                                           message=f"Could not read {name}: {exc}", progress=job.progress))
                continue
            hints: List[str] = [Path(name).stem.replace("_", " ")]   # the file name is a strong title hint
            if kind == "dxf":
                try:
                    hints = paperspace_hints(load_dxf(path))
                except Exception as exc:  # noqa: BLE001
                    log.info("paperspace hints failed for %s: %s", name, exc)
            for inv in invs:
                rec = SheetRecord(id=new_id(), job_id=job.id, file_name=name, page_no=inv.page_no, layout=inv.layout,
                                  classification=classify_sheet_heuristic(inv, hints + title_block_hints(inv)),
                                  text_count=len(inv.texts), width=inv.width, height=inv.height,
                                  processing_notes=list(inv.notes))
                sh = _Sheet(rec, inv, kind, path)
                sh.hints = hints
                try:
                    if kind == "pdf":
                        png = render_page_png(path, inv.page_no, max_px=s.gemini_max_image_px, dpi=s.preview_dpi)
                    elif kind == "dxf":
                        png = render_layout_png(path, inv.layout, max_px=s.gemini_max_image_px, dpi=s.preview_dpi)
                    else:
                        png = render_image_png(path, inv.page_no, max_px=s.gemini_max_image_px)
                    sh.hi_png = png
                    pv = previews / f"{rec.id}.png"
                    pv.write_bytes(_downscale(png, 1600))
                    rec.preview_path = get_storage().store(pv, "previews", f"{job.id}/{rec.id}.png")
                except Exception as exc:  # noqa: BLE001
                    rec.processing_notes.append(f"preview failed: {exc}")
                sheets.append(sh)
        if not sheets:
            raise RuntimeError("No sheets could be read from the uploaded files")
        return sheets

    # ------------------------------------------------------------------ stage 3: classify
    def _classify(self, job: JobRecord, sheets: List[_Sheet], ai: GeminiClient) -> None:
        n = len(sheets)
        for i, sh in enumerate(sheets):
            heur = sh.record.classification
            if ai.enabled and sh.hi_png:
                try:
                    res = ai.generate_json(
                        AISheetClass,
                        classify_prompt(sh.record.file_name, sh.record.page_no, sh.title_hints(),
                                        sh.inv.to_prompt_text(max_items=220)),
                        images=[_downscale(sh.hi_png, 1600)], tier="fast", system=SYSTEM, max_output_tokens=2048,
                    )
                    cls = classification_from_ai(res)
                    # keep the deterministic unit guess when the model is unsure
                    if cls.units == "unknown":
                        cls.units = heur.units
                    if cls.drawing_number is None:
                        cls.drawing_number = heur.drawing_number
                    sh.record.classification = cls
                except GeminiUnavailable as exc:
                    sh.record.processing_notes.append(f"AI classification unavailable: {exc}")
                except Exception as exc:  # noqa: BLE001
                    sh.record.processing_notes.append(f"AI classification failed: {exc}")
            if i % 3 == 2 or i == n - 1:
                self._event(job, JobStatus.analysing, f"Classified {i + 1}/{n} sheets", 25 + int(18 * (i + 1) / n))
        for sh in sheets:
            c = sh.record.classification
            if c.drawing_number and c.drawing_number not in job.drawing_refs:
                job.drawing_refs.append(c.drawing_number)

    # ------------------------------------------------------------------ stage 4a: structural
    def _extract_structural(self, job: JobRecord, sheets: List[_Sheet], ai: GeminiClient) -> None:
        import re as _re
        _callout = _re.compile(r"\b\d{1,2}\s*-?\s*[TY#]\s*\d{1,2}\b|\b[TY]\s*\d{1,2}\s*@\s*\d{2,3}", _re.I)
        relevant = [sh for sh in sheets if sh.record.classification.relevant_for_bbs
                    or sh.record.classification.discipline == "structural"
                    or len(_callout.findall(sh.inv.all_text())) >= 3]
        for sh in relevant:
            sh.record.classification.relevant_for_bbs = True
        if not relevant:
            relevant = [sh for sh in sheets if sh.inv.texts]
            job.events.append(JobEvent(at=datetime.utcnow(), status=JobStatus.extracting,
                                       message="No sheet was classified as structural; trying every sheet with text",
                                       progress=job.progress))
        parts: List[StructuralExtraction] = []
        known_notes = ""
        n = len(relevant)
        for i, sh in enumerate(relevant):
            c = sh.record.classification
            tables = tables_to_prompt(reconstruct_tables(sh.inv))
            part: Optional[StructuralExtraction] = None
            if ai.enabled and sh.hi_png:
                try:
                    res = ai.generate_json(
                        AIStructuralExtraction,
                        structural_prompt(sh.label, c.units, tables, sh.inv.to_prompt_text(), known_notes),
                        images=[sh.hi_png], tier="pro", system=SYSTEM, max_output_tokens=65536, temperature=0.05,
                    )
                    part = structural_from_ai(res, sh.label)
                    gn = part.general_notes
                    bits = [f"{k}={v}" for k, v in gn.model_dump().items() if v not in (None, [], "")]
                    if bits:
                        known_notes = "; ".join(bits)[:400]
                except (GeminiUnavailable, Exception) as exc:  # noqa: BLE001
                    sh.record.processing_notes.append(f"AI extraction failed, heuristic used: {exc}")
            if part is None:
                part = structural_members_heuristic(sh.inv, sh.label)
            sh.record.extraction = part
            parts.append(part)
            self._event(job, JobStatus.extracting,
                        f"{sh.label}: {part.member_count()} member(s) read", 45 + int(40 * (i + 1) / max(n, 1)))
        merged = merge_structural(parts)
        job.members = list(merged.beams) + list(merged.slabs) + list(merged.columns) + list(merged.walls) + list(merged.stairs)
        job.general_notes = merged.general_notes
        gn = merged.general_notes
        applied = []
        if gn.ld_factor and gn.ld_factor != job.standards.ld_factor:
            job.standards.ld_factor = gn.ld_factor; applied.append(f"Ld={gn.ld_factor}d")
        for f in ("cover_beam_mm", "cover_slab_mm", "cover_column_mm"):
            v = getattr(gn, f)
            if v and v != getattr(job.standards, f):
                setattr(job.standards, f, v); applied.append(f"{f}={v}")
        if applied:
            job.events.append(JobEvent(at=datetime.utcnow(), status=JobStatus.extracting,
                                       message="Standards taken from drawing notes: " + ", ".join(applied), progress=job.progress))
        for w in merged.warnings[:20]:
            job.events.append(JobEvent(at=datetime.utcnow(), status=JobStatus.extracting, message=w, progress=job.progress))
        if not job.members:
            job.events.append(JobEvent(at=datetime.utcnow(), status=JobStatus.extracting,
                                       message="No members were read. Add members manually or enable AI reading.", progress=job.progress))

    # ------------------------------------------------------------------ stage 4b: fit-out
    def _extract_fitout(self, job: JobRecord, sheets: List[_Sheet], sources: List[Tuple[str, str, Path]],
                        ai: GeminiClient) -> None:
        dxf_by_stem: Dict[str, Path] = {p.stem.lower(): p for (_n, k, p) in sources if k == "dxf"}
        xref_cache: Dict[str, MeasuredFacts] = {}
        # measured facts
        for sh in sheets:
            try:
                if sh.kind == "dxf" and sh.record.layout == "Model":
                    facts = measure_dxf(sh.path, sh.inv)
                    for note in list(facts.notes):
                        if note.startswith("xrefs referenced"):
                            for xr in note.split(":", 1)[1].split(","):
                                key = xr.strip().lower()
                                if key in dxf_by_stem and key != sh.path.stem.lower():
                                    if key not in xref_cache:
                                        xref_cache[key] = measure_dxf(dxf_by_stem[key])
                                    xf = xref_cache[key]
                                    facts.hatches.extend(xf.hatches)
                                    facts.rooms.extend(r for r in xf.rooms if r.name not in {x.name for x in facts.rooms})
                                    facts.notes.append(f"included geometry from uploaded xref {dxf_by_stem[key].name}")
                    sh.facts = facts
                else:
                    sh.facts = measure_from_inventory(sh.inv)
            except Exception as exc:  # noqa: BLE001
                sh.record.processing_notes.append(f"geometry measurement failed: {exc}")
                sh.facts = MeasuredFacts(source=sh.label)
        def _measurable(sh: _Sheet) -> bool:
            f = sh.facts
            if f is None:
                return False
            has_codes = any(h.code for h in f.hatches) or bool(f.code_counts) or bool(f.length_by_layer_m)
            return has_codes or len(f.rooms) >= 2
        relevant = [sh for sh in sheets if sh.record.classification.relevant_for_boq or _measurable(sh)]
        for sh in relevant:
            if not sh.record.classification.relevant_for_boq:
                sh.record.classification.relevant_for_boq = True
                sh.record.processing_notes.append("marked measurable from CAD facts (finish codes / tags / lengths found)")
        if not relevant:
            relevant = [sh for sh in sheets if sh.inv.texts or (sh.facts and not sh.facts.is_empty())]
            job.events.append(JobEvent(at=datetime.utcnow(), status=JobStatus.extracting,
                                       message="No sheet was classified as measurable; trying every sheet", progress=job.progress))
        parts: List[FitoutExtraction] = []
        legend: Dict[str, str] = {}
        n = len(relevant)
        for i, sh in enumerate(relevant):
            c = sh.record.classification
            part: Optional[FitoutExtraction] = None
            facts_txt = sh.facts.to_prompt_text() if sh.facts else "(none)"
            if ai.enabled and sh.hi_png:
                try:
                    known = "; ".join(f"{k}: {v}" for k, v in list(legend.items())[:80])
                    res = ai.generate_json(
                        AIFitoutExtraction,
                        fitout_prompt(sh.label, c.sheet_type, c.units, facts_txt, sh.inv.to_prompt_text(), known),
                        images=[sh.hi_png], tier="pro", system=SYSTEM, max_output_tokens=65536, temperature=0.05,
                    )
                    part = fitout_from_ai(res, sh.label)
                    legend.update(part.legend)
                except (GeminiUnavailable, Exception) as exc:  # noqa: BLE001
                    sh.record.processing_notes.append(f"AI extraction failed, measured facts used: {exc}")
            if part is None:
                part = fitout_items_from_facts(sh.facts or MeasuredFacts(source=sh.label), sh.label, c.sheet_type)
            sh.record.fitout_extraction = part
            parts.append(part)
            self._event(job, JobStatus.extracting, f"{sh.label}: {len(part.items)} item(s), {len(part.rooms)} room(s)",
                        45 + int(40 * (i + 1) / max(n, 1)))
        merged = merge_fitout(parts)
        job.fitout_items = merged.items
        job.rooms = merged.rooms
        job.legend = merged.legend
        for w in merged.warnings[:20]:
            job.events.append(JobEvent(at=datetime.utcnow(), status=JobStatus.extracting, message=w, progress=job.progress))


# ---------------------------------------------------------------------- shared
def recalculate(job: JobRecord) -> JobRecord:
    """Deterministic quantification; also invalidates any cached export."""
    if job.module == Module.structural:
        job.result = compute_bbs(job.members, job.standards, job.level)
        job.boq = None
    else:
        job.boq = compute_boq(job.fitout_items, job.rooms, job.currency)
        job.result = None
    job.export_path = None
    return job


def _downscale(png: bytes, max_px: int) -> bytes:
    try:
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(png))
        if max(im.size) <= max_px:
            return png
        r = max_px / max(im.size)
        im = im.convert("RGB").resize((max(1, int(im.width * r)), max(1, int(im.height * r))))
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception:
        return png
