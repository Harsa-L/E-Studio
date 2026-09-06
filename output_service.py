"""Print and PDF output adapters sharing the canvas rendering boundary."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QMarginsF, QRectF, QSizeF
from PySide6.QtGui import QPainter, QPageLayout, QPageSize, QPdfWriter
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog


class OutputService:
    @staticmethod
    def print_preview(canvas, parent=None, data_record: dict[str, Any] | None = None) -> bool:
        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintPreviewDialog(printer, parent)

        def render_preview(device):
            painter = QPainter(device)
            try:
                target = printer.pageRect(QPrinter.DevicePixel)
                canvas._render_output(painter, data_record, QRectF(target))
            finally:
                painter.end()

        dialog.paintRequested.connect(render_preview)
        return dialog.exec() == QPrintPreviewDialog.Accepted

    @staticmethod
    def export_pdf(canvas, path: str, dpi: float = 300.0, data_record: dict[str, Any] | None = None) -> None:
        if dpi <= 0:
            raise ValueError("DPI must be greater than zero.")
        writer = QPdfWriter(path)
        writer.setResolution(round(dpi))
        writer.setPageSize(QPageSize(QSizeF(canvas.template.width_mm, canvas.template.height_mm), QPageSize.Millimeter))
        writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Millimeter)
        painter = QPainter(writer)
        try:
            canvas._render_output(painter, data_record, QRectF(0, 0, canvas.template.width_mm * dpi / 25.4, canvas.template.height_mm * dpi / 25.4))
        finally:
            painter.end()

    @staticmethod
    def print_label(canvas, parent=None, data_record: dict[str, Any] | None = None) -> bool:
        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, parent)
        if dialog.exec() != QPrintDialog.Accepted:
            return False
        painter = QPainter(printer)
        try:
            target = printer.pageRect(QPrinter.DevicePixel)
            canvas._render_output(painter, data_record, QRectF(target))
        finally:
            painter.end()
        return True
