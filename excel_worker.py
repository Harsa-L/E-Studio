"""Qt worker for non-blocking Excel reading and row normalization."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from batch_export import BatchReport, normalize_workbook
from binding_profiles import BindingProfile
from data_sources import WorkbookReadError, WorkbookTable, read_xlsx


class ExcelNormalizeWorker(QObject):
    """Run workbook I/O and normalization away from the editor thread."""

    progress = Signal(int, int)
    finished = Signal(object, object)
    failed = Signal(str)

    def __init__(self, path: str | None, profile: BindingProfile, sheet_name: str | None = None, table: WorkbookTable | None = None):
        super().__init__()
        self.path = path
        self.profile = profile
        self.sheet_name = sheet_name
        self.table = table
        self._cancelled = False

    @Slot()
    def run(self):
        try:
            table: WorkbookTable = self.table or read_xlsx(self.path, self.sheet_name)
            report: BatchReport = normalize_workbook(
                table,
                self.profile,
                progress=self._report_progress,
            )
            self.finished.emit(table, report)
        except Exception as error:
            self.failed.emit(str(error))

    def _report_progress(self, current: int, total: int) -> bool:
        if self._cancelled:
            return False
        self.progress.emit(current, total)
        return not self._cancelled

    @Slot()
    def cancel(self):
        self._cancelled = True