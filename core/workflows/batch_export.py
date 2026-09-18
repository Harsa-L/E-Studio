"""Row-isolated orchestration for spreadsheet-backed label exports."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable
import csv
import json

from core.workflows.binding_profiles import BindingProfile
from core.workflows.data_normalization import RowNormalizationResult, normalize_row
from core.workflows.data_sources import ImportedRow, ImportIssue, WorkbookTable
from core.rendering.imposition import ImpositionCalculator


@dataclass(frozen=True)
class BatchRowResult:
    row_number: int
    record: dict[str, Any] | None
    issues: list[ImportIssue]
    output_name: str | None = None

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


@dataclass
class BatchReport:
    results: list[BatchRowResult]

    @property
    def succeeded(self) -> int:
        return sum(result.valid for result in self.results)

    @property
    def failed(self) -> int:
        return len(self.results) - self.succeeded

    def to_json(self) -> str:
        return json.dumps(
            {
                "succeeded": self.succeeded,
                "failed": self.failed,
                "rows": [
                    {
                        "row_number": result.row_number,
                        "record": result.record,
                        "output_name": result.output_name,
                        "issues": [asdict(issue) for issue in result.issues],
                    }
                    for result in self.results
                ],
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    def write_csv(self, path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=["row_number", "status", "output_name", "issues"])
            writer.writeheader()
            for result in self.results:
                writer.writerow({
                    "row_number": result.row_number,
                    "status": "ok" if result.valid else "error",
                    "output_name": result.output_name or "",
                    "issues": "; ".join(issue.message for issue in result.issues),
                })

    def write_manifest(self, path: str, output_directory: str, format_name: str) -> None:
        payload = {
            "format": format_name,
            "output_directory": str(output_directory),
            "succeeded": self.succeeded,
            "failed": self.failed,
            "outputs": [
                {"row_number": result.row_number, "file": result.output_name, "status": "ok" if result.valid else "error"}
                for result in self.results
                if result.output_name
            ],
        }
        with open(path, "w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2, ensure_ascii=False)


def _available_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    index = 2
    while True:
        candidate = directory / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def normalize_workbook(
    table: WorkbookTable,
    profile: BindingProfile,
    error_policy: str = "skip_invalid_rows",
    output_name: Callable[[ImportedRow], str] | None = None,
    progress: Callable[[int, int], bool] | None = None,
) -> BatchReport:
    """Normalize all rows and apply a predictable row-level error policy.

    ``fail_fast`` raises on the first invalid row. The other policies preserve
    every row in the report so the UI can explain exactly what was skipped.
    """
    if error_policy not in {"fail_fast", "skip_invalid_rows", "export_with_warnings"}:
        raise ValueError(f"Unsupported error policy: {error_policy}")
    if errors := profile.validate(set(table.headers)):
        issues = [ImportIssue("mapping_error", message) for message in errors]
        if error_policy == "fail_fast":
            raise ValueError("Invalid binding profile: " + "; ".join(errors))
        return BatchReport([BatchRowResult(0, None, issues)])

    results: list[BatchRowResult] = []
    rows = list(table.iter_rows())
    total = len(rows)
    for index, row in enumerate(rows, 1):
        if progress and not progress(index - 1, total):
            break
        normalized: RowNormalizationResult = normalize_row(row, profile)
        if not normalized.valid and error_policy == "fail_fast":
            raise ValueError(f"Row {row.row_number} is invalid: " + "; ".join(issue.message for issue in normalized.issues))
        record = normalized.record if normalized.valid or error_policy == "export_with_warnings" else None
        results.append(BatchRowResult(row.row_number, record, normalized.issues, output_name(row) if output_name else None))
    return BatchReport(results)


def export_rows_as_png(
    canvas,
    report: BatchReport,
    output_directory: str,
    dpi: float = 300.0,
    progress: Callable[[int, int], bool] | None = None,
) -> BatchReport:
    """Render valid normalized rows individually without mutating the template."""
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    results: list[BatchRowResult] = []
    total = len(report.results)
    for index, result in enumerate(report.results, 1):
        if progress and not progress(index - 1, total):
            break
        if not result.valid or result.record is None:
            results.append(result)
            continue
        filename = result.output_name or f"label_{result.row_number:05d}.png"
        if not filename.lower().endswith(".png"):
            filename += ".png"
        target = _available_path(directory, filename)
        try:
            canvas.export_png(str(target), dpi=dpi, data_record=result.record)
            results.append(BatchRowResult(result.row_number, result.record, result.issues, target.name))
        except (OSError, ValueError, TypeError) as error:
            issue = ImportIssue("export_error", str(error), "error", row_number=result.row_number)
            results.append(BatchRowResult(result.row_number, result.record, [*result.issues, issue], filename))
    return BatchReport(results)


def export_rows_on_pages(
    canvas,
    report: BatchReport,
    output_directory: str,
    page_size_name: str = "A4",
    gap_mm: float = 0.0,
    dpi: float = 300.0,
    progress: Callable[[int, int], bool] | None = None,
) -> BatchReport:
    """Place different valid records on successive labels across page PNGs."""
    from tempfile import TemporaryDirectory
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QImage, QPainter

    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    layout = ImpositionCalculator.calculate(
        canvas.template.width_mm,
        canvas.template.height_mm,
        canvas.template.outer_margins_mm,
        page_size_name,
        gap_mm,
    )
    page_w_mm, page_h_mm = ImpositionCalculator.PAGE_SIZES[page_size_name.upper()]
    valid = [result for result in report.results if result.valid and result.record is not None]
    results: list[BatchRowResult] = [result for result in report.results if not result.valid or result.record is None]
    labels_per_page = layout.total_per_page
    total = len(valid)
    with TemporaryDirectory() as temporary:
        for page_index in range(0, total, labels_per_page):
            page_number = page_index // labels_per_page + 1
            output_path = _available_path(directory, f"sheet_{page_number:03d}.png")
            output_name = output_path.name
            page = QImage(round(page_w_mm * dpi / 25.4), round(page_h_mm * dpi / 25.4), QImage.Format_ARGB32_Premultiplied)
            page.fill(Qt.white)
            page.setDotsPerMeterX(round(dpi / 0.0254))
            page.setDotsPerMeterY(round(dpi / 0.0254))
            painter = QPainter(page)
            page_results = valid[page_index:page_index + labels_per_page]
            page_result_start = len(results)
            for slot, result in enumerate(page_results):
                progress_index = page_index + slot
                if progress and not progress(progress_index, total):
                    painter.end()
                    return BatchReport(results)
                temp_path = Path(temporary) / f"row_{result.row_number}.png"
                try:
                    canvas.export_png(str(temp_path), dpi=dpi, data_record=result.record)
                    label = QImage(str(temp_path))
                    row = slot // layout.cols
                    column = slot % layout.cols
                    outer = canvas.template.outer_margins_mm
                    x_mm = layout.horizontal_offset_mm + outer.left + column * (canvas.template.width_mm + outer.left + outer.right + gap_mm)
                    y_mm = layout.vertical_offset_mm + outer.top + row * (canvas.template.height_mm + outer.top + outer.bottom + gap_mm)
                    painter.drawImage(QRectF(x_mm * dpi / 25.4, y_mm * dpi / 25.4, label.width(), label.height()), label)
                    results.append(BatchRowResult(result.row_number, result.record, result.issues, output_name))
                except (OSError, ValueError, TypeError) as error:
                    results.append(BatchRowResult(result.row_number, result.record, [*result.issues, ImportIssue("export_error", str(error), "error", row_number=result.row_number)], output_name))
            painter.end()
            if not page.save(str(output_path), "PNG"):
                del results[page_result_start:]
                results.extend(BatchRowResult(item.row_number, item.record, [*item.issues, ImportIssue("export_error", f"Unable to write {output_path}", "error", row_number=item.row_number)], output_name) for item in page_results)
    return BatchReport(results)
