"""Canvas de disposition créé uniquement sur base d'un Gabarit validé."""

from typing import Any, Dict, List
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QImage, QPainter, QColor, QPen
from PySide6.QtWidgets import QGraphicsScene

from template_model import LabelTemplate
from label_items import BaseLabelItem, HazardWarningOverlay
from imposition import ImpositionCalculator


class TemplateCanvas(QGraphicsScene):
    """Canvas graphique avec zone neutre élargie, contrôle des marges et exclusion."""

    document_changed = Signal()

    WORKSPACE_PADDING_MM = 15.0

    def __init__(self, template: LabelTemplate, scale_px_per_mm: float = 3.78):
        super().__init__()
        self.template = template
        self.scale = scale_px_per_mm

        self.warning_overlays: List[HazardWarningOverlay] = []
        self.load_warnings: List[Dict[str, Any]] = []
        self.last_validation_report: List[Dict[str, Any]] = []
        self.preview_data: Dict[str, Any] = {}
        self.preview_enabled = False
        self.show_background_reference = True

        w_px = self.template.width_mm * self.scale
        h_px = self.template.height_mm * self.scale

        m_out = self.template.outer_margins_mm
        m_in = self.template.inner_margins_mm

        self.label_rect = QRectF(0, 0, w_px, h_px)

        self.outer_rect = QRectF(
            -m_out.left * self.scale,
            -m_out.top * self.scale,
            w_px + (m_out.left + m_out.right) * self.scale,
            h_px + (m_out.top + m_out.bottom) * self.scale
        )

        self.inner_rect = QRectF(
            m_in.left * self.scale,
            m_in.top * self.scale,
            w_px - (m_in.left + m_in.right) * self.scale,
            h_px - (m_in.top + m_in.bottom) * self.scale
        )

        # La taille du canvas est plus grande que le gabarit + marges externes
        pad_px = self.WORKSPACE_PADDING_MM * self.scale
        self.canvas_bounds = self.outer_rect.adjusted(-pad_px, -pad_px, pad_px, pad_px)
        self.setSceneRect(self.canvas_bounds)

        for item_data in self.template.items:
            try:
                self.addItem(BaseLabelItem.from_dict(item_data, self.scale))
            except (KeyError, TypeError, ValueError) as error:
                self.load_warnings.append({"item": item_data, "error": str(error)})

    def addItem(self, item):
        super().addItem(item)
        if isinstance(item, BaseLabelItem):
            item.item_changed.connect(self.document_changed)
            if self.preview_enabled and hasattr(item, "set_export_record"):
                item.set_export_record(self.preview_data)
            self.document_changed.emit()

    def removeItem(self, item):
        super().removeItem(item)
        if isinstance(item, BaseLabelItem):
            self.document_changed.emit()

    def set_preview_data(self, data_record: Dict[str, Any], enabled: bool = True) -> None:
        self.preview_data = dict(data_record)
        self.preview_enabled = enabled
        for item in self.items():
            if isinstance(item, BaseLabelItem) and hasattr(item, "set_export_record"):
                item.set_export_record(self.preview_data if enabled else None)

    def delete_selected_items(self) -> int:
        selected = [item for item in self.selectedItems() if isinstance(item, BaseLabelItem)]
        for item in selected:
            self.removeItem(item)
        return len(selected)

    def item_snapshot(self) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in self.items() if isinstance(item, BaseLabelItem)]

    def restore_item_snapshot(self, snapshot: List[Dict[str, Any]]) -> None:
        for item in list(self.items()):
            if isinstance(item, BaseLabelItem):
                self.removeItem(item)
        self.clearSelection()
        for data in snapshot:
            self.addItem(BaseLabelItem.from_dict(data, self.scale))
        self.document_changed.emit()

    def _selected_items(self) -> List[BaseLabelItem]:
        return [item for item in self.selectedItems() if isinstance(item, BaseLabelItem)]

    def align_items(self, mode: str) -> int:
        selected = self._selected_items()
        if len(selected) < 2:
            return 0
        bounds = [item.sceneBoundingRect() for item in selected]
        left = min(rect.left() for rect in bounds)
        right = max(rect.right() for rect in bounds)
        top = min(rect.top() for rect in bounds)
        bottom = max(rect.bottom() for rect in bounds)
        for item, rect in zip(selected, bounds):
            if mode == "left":
                item.set_x_mm(left / self.scale)
            elif mode == "center_horizontal":
                item.set_x_mm((left + (right - left - rect.width()) / 2) / self.scale)
            elif mode == "right":
                item.set_x_mm((right - rect.width()) / self.scale)
            elif mode == "top":
                item.set_y_mm(top / self.scale)
            elif mode == "center_vertical":
                item.set_y_mm((top + (bottom - top - rect.height()) / 2) / self.scale)
            elif mode == "bottom":
                item.set_y_mm((bottom - rect.height()) / self.scale)
            else:
                raise ValueError(f"Unsupported alignment mode: {mode}")
        self.document_changed.emit()
        return len(selected)

    def distribute_items(self, direction: str) -> int:
        selected = self._selected_items()
        if len(selected) < 3:
            return 0
        selected.sort(key=lambda item: item.scenePos().x() if direction == "horizontal" else item.scenePos().y())
        first = selected[0].scenePos()
        last = selected[-1].scenePos()
        start = first.x() if direction == "horizontal" else first.y()
        end = last.x() if direction == "horizontal" else last.y()
        step = (end - start) / (len(selected) - 1)
        for index, item in enumerate(selected[1:-1], 1):
            value = (start + step * index) / self.scale
            if direction == "horizontal":
                item.set_x_mm(value)
            else:
                item.set_y_mm(value)
        self.document_changed.emit()
        return len(selected)

    def duplicate_selected_items(self) -> int:
        selected = [item for item in self.selectedItems() if isinstance(item, BaseLabelItem)]
        duplicates = []
        for item in selected:
            data = item.to_dict()
            data["id"] = self.next_item_id(data["id"].rsplit("_", 1)[0])
            data["x_mm"] = float(data["x_mm"]) + 5.0
            data["y_mm"] = float(data["y_mm"]) + 5.0
            duplicate = BaseLabelItem.from_dict(data, self.scale)
            duplicates.append(duplicate)
        self.clearSelection()
        for duplicate in duplicates:
            self.addItem(duplicate)
            duplicate.setSelected(True)
        return len(duplicates)

    def drawBackground(self, painter: QPainter, rect: QRectF):
        painter.save()

        # 1. Espace neutre gris
        painter.fillRect(rect, QColor("#2B2B2B"))

        # 2. Débordement / Marges externes
        painter.fillRect(self.outer_rect, QColor("#FFEBEE"))
        painter.setPen(QPen(QColor("#EF5350"), 1, Qt.DashLine))
        painter.drawRect(self.outer_rect)

        # 3. Surface de l'étiquette
        bg_col = QColor(self.template.bg_color)
        bg_col.setAlphaF(self.template.bg_opacity)
        painter.fillRect(self.label_rect, bg_col)
        self._draw_background_reference(painter)
        painter.setPen(QPen(QColor("#000000"), 1.5))
        painter.drawRect(self.label_rect)

        # 4. Zone utile imprimable
        painter.setPen(QPen(QColor("#2196F3"), 1, Qt.DotLine))
        painter.drawRect(self.inner_rect)

        painter.restore()

    def _draw_background_reference(self, painter: QPainter) -> None:
        path = self.template.background_image_path
        if not self.show_background_reference or not self.template.background_image_visible or not path:
            return
        image = QImage(path)
        if image.isNull():
            return
        target = self.label_rect
        if self.template.background_image_fit == "stretch":
            painter.save()
            painter.setOpacity(self.template.background_image_opacity)
            painter.drawImage(target, image)
            painter.restore()
            return
        scaled = image.scaled(target.size().toSize(), Qt.KeepAspectRatio if self.template.background_image_fit == "contain" else Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.save()
        painter.setOpacity(self.template.background_image_opacity)
        painter.setClipRect(target)
        painter.drawImage(QRectF(target.center().x() - scaled.width() / 2, target.center().y() - scaled.height() / 2, scaled.width(), scaled.height()), scaled)
        painter.restore()

    def validate_item_bounds(self) -> List[BaseLabelItem]:
        """Affiche les bandes d'avertissement clignotantes pour les objets hors-limites."""
        for overlay in self.warning_overlays:
            self.removeItem(overlay)
        self.warning_overlays.clear()
        self.last_validation_report = []

        faulty_items = []
        for item in self.items():
            if isinstance(item, BaseLabelItem):
                item_rect = item.mapToScene(item.boundingRect()).boundingRect()
                if not self.inner_rect.contains(item_rect):
                    faulty_items.append(item)
                    self.last_validation_report.append({
                        "id": item.item_id,
                        "reason": "outside_printable_area",
                    })
                    overlay = HazardWarningOverlay(item_rect)
                    self.addItem(overlay)
                    self.warning_overlays.append(overlay)

        return faulty_items

    def next_item_id(self, prefix: str) -> str:
        """Return a stable, collision-free identifier for a newly inserted item."""
        used_ids = {item.item_id for item in self.items() if isinstance(item, BaseLabelItem)}
        index = 1
        while f"{prefix}_{index}" in used_ids:
            index += 1
        return f"{prefix}_{index}"

    def export_png(self, path: str, dpi: float = 300.0, data_record: Dict[str, Any] | None = None) -> None:
        """Render the label area to a print-resolution PNG.

        Rich items receive ``data_record`` during this render only.  The
        editor objects stay unchanged, so preview data cannot accidentally alter
        the saved template.
        """
        if dpi <= 0:
            raise ValueError("DPI must be greater than zero.")
        width_px = max(1, round(self.template.width_mm * dpi / 25.4))
        height_px = max(1, round(self.template.height_mm * dpi / 25.4))
        image = QImage(width_px, height_px, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        image.setDotsPerMeterX(round(dpi / 0.0254))
        image.setDotsPerMeterY(round(dpi / 0.0254))

        bound_items = [item for item in self.items() if hasattr(item, "set_export_record")]
        selected_items = [item for item in self.selectedItems() if isinstance(item, BaseLabelItem)]
        overlay_visibility = [(overlay, overlay.isVisible()) for overlay in self.warning_overlays]
        for overlay, _ in overlay_visibility:
            overlay.hide()
        for item in selected_items:
            item.setSelected(False)
        for item in bound_items:
            item.set_export_record(data_record or {})

        reference_visibility = self.show_background_reference
        self.show_background_reference = False
        try:
            painter = QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)
            self.render(painter, QRectF(0, 0, width_px, height_px), self.label_rect)
            painter.end()
        finally:
            for item in bound_items:
                item.set_export_record(self.preview_data if self.preview_enabled else None)
            for item in selected_items:
                item.setSelected(True)
            for overlay, was_visible in overlay_visibility:
                overlay.setVisible(was_visible)
            self.show_background_reference = reference_visibility

        if not image.save(path, "PNG"):
            raise OSError(f"Unable to write PNG file: {path}")

    def _render_output(self, painter: QPainter, data_record: Dict[str, Any] | None, target: QRectF) -> None:
        """Render one output record while suppressing editor-only visuals."""
        bound_items = [item for item in self.items() if hasattr(item, "set_export_record")]
        selected_items = [item for item in self.selectedItems() if isinstance(item, BaseLabelItem)]
        overlay_visibility = [(overlay, overlay.isVisible()) for overlay in self.warning_overlays]
        reference_visibility = self.show_background_reference
        self.show_background_reference = False
        for overlay, _ in overlay_visibility:
            overlay.hide()
        for item in selected_items:
            item.setSelected(False)
        for item in bound_items:
            item.set_export_record(data_record or {})
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)
            self.render(painter, target, self.label_rect)
        finally:
            for item in bound_items:
                item.set_export_record(self.preview_data if self.preview_enabled else None)
            for item in selected_items:
                item.setSelected(True)
            for overlay, was_visible in overlay_visibility:
                overlay.setVisible(was_visible)
            self.show_background_reference = reference_visibility

    def export_page_png(
        self,
        path: str,
        page_size_name: str = "A4",
        gap_mm: float = 0.0,
        dpi: float = 300.0,
        data_record: Dict[str, Any] | None = None,
    ) -> None:
        """Render repeated labels centered on a physical page."""
        if dpi <= 0:
            raise ValueError("DPI must be greater than zero.")
        layout = ImpositionCalculator.calculate(
            self.template.width_mm,
            self.template.height_mm,
            self.template.outer_margins_mm,
            page_size_name,
            gap_mm,
        )
        page_w_mm, page_h_mm = ImpositionCalculator.PAGE_SIZES[page_size_name.upper()]
        page = QImage(
            max(1, round(page_w_mm * dpi / 25.4)),
            max(1, round(page_h_mm * dpi / 25.4)),
            QImage.Format_ARGB32_Premultiplied,
        )
        page.fill(Qt.white)
        page.setDotsPerMeterX(round(dpi / 0.0254))
        page.setDotsPerMeterY(round(dpi / 0.0254))

        bound_items = [item for item in self.items() if hasattr(item, "set_export_record")]
        selected_items = [item for item in self.selectedItems() if isinstance(item, BaseLabelItem)]
        overlay_visibility = [(overlay, overlay.isVisible()) for overlay in self.warning_overlays]
        for overlay, _ in overlay_visibility:
            overlay.hide()
        for item in selected_items:
            item.setSelected(False)
        for item in bound_items:
            item.set_export_record(data_record or {})

        reference_visibility = self.show_background_reference
        self.show_background_reference = False
        try:
            painter = QPainter(page)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)
            label_w_px = self.template.width_mm * dpi / 25.4
            label_h_px = self.template.height_mm * dpi / 25.4
            outer = self.template.outer_margins_mm
            for row in range(layout.rows):
                for column in range(layout.cols):
                    x_mm = layout.horizontal_offset_mm + outer.left + column * (
                        self.template.width_mm + outer.left + outer.right + gap_mm
                    )
                    y_mm = layout.vertical_offset_mm + outer.top + row * (
                        self.template.height_mm + outer.top + outer.bottom + gap_mm
                    )
                    target = QRectF(
                        x_mm * dpi / 25.4,
                        y_mm * dpi / 25.4,
                        label_w_px,
                        label_h_px,
                    )
                    self.render(painter, target, self.label_rect)
            painter.end()
        finally:
            for item in bound_items:
                item.set_export_record(self.preview_data if self.preview_enabled else None)
            for item in selected_items:
                item.setSelected(True)
            for overlay, was_visible in overlay_visibility:
                overlay.setVisible(was_visible)
            self.show_background_reference = reference_visibility

        if not page.save(path, "PNG"):
            raise OSError(f"Unable to write PNG file: {path}")

    def finalize_and_save_template(self) -> str:
        """Sauvegarde le Gabarit en EXCLUANT les objets hors-limites."""
        faulty_items = self.validate_item_bounds()
        valid_data = []

        for item in self.items():
            if isinstance(item, BaseLabelItem) and item not in faulty_items:
                valid_data.append(item.to_dict())

        return self._serialize_items(valid_data)

    def serialize_current_template(self) -> str:
        """Serialize the complete editable document for autosave/recovery."""
        return self._serialize_items(self.item_snapshot())

    def _serialize_items(self, items: List[dict]) -> str:
        previous_items = self.template.items
        try:
            self.template.items = items
            return self.template.to_json()
        finally:
            self.template.items = previous_items
