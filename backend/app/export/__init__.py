"""Excel export layer: JobRecord -> .xlsx.
measurement (the product) -> Measurement Sheet / BOQ / Materials workbook;
fitout (legacy) -> KR-style BOQ; structural (legacy) -> BBS."""
from __future__ import annotations

from pathlib import Path

from app.export.bbs_xlsx import write_bbs_workbook
from app.export.boq_xlsx import write_boq_workbook
from app.export.measurement_xlsx import write_measurement_workbook
from app.models.schemas import JobRecord, Module


def write_workbook(job: JobRecord, path: Path) -> Path:
    module = job.module.value if isinstance(job.module, Module) else str(job.module)
    if module == Module.measurement.value:
        return write_measurement_workbook(job, Path(path))
    if module == Module.fitout.value:
        return write_boq_workbook(job, Path(path))
    return write_bbs_workbook(job, Path(path))


__all__ = ["write_workbook", "write_bbs_workbook", "write_boq_workbook", "write_measurement_workbook"]
