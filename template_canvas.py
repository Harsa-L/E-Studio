"""Canvas de disposition créé uniquement sur base d'un Gabarit validé."""

from typing import Any, Dict, List
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QColor, QPen
from PySide6.QtWidgets import QGraphicsScene

from template_model import LabelTemplate
from label_items import BaseLabelItem, HazardWarningOverlay


class TemplateCanvas(QGraphicsScene):
    """Canvas graphique avec zone neutre élargie, contrôle des marges et exclusion."""

    WORKSPACE_PADDING_MM = 15.0

    def __init__(self, template: LabelTemplate, scale_px_per_mm: float = 3.78):
        super().__init__()
        self.template = template
        self.scale = scale_px_per_mm

        self.warning_overlays: List[HazardWarningOverlay] = []

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
            except (KeyError, TypeError, ValueError):
                continue

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
        painter.setPen(QPen(QColor("#000000"), 1.5))
        painter.drawRect(self.label_rect)

        # 4. Zone utile imprimable
        painter.setPen(QPen(QColor("#2196F3"), 1, Qt.DotLine))
        painter.drawRect(self.inner_rect)

        painter.restore()

    def validate_item_bounds(self) -> List[BaseLabelItem]:
        """Affiche les bandes d'avertissement clignotantes pour les objets hors-limites."""
        for overlay in self.warning_overlays:
            self.removeItem(overlay)
        self.warning_overlays.clear()

        faulty_items = []
        for item in self.items():
            if isinstance(item, BaseLabelItem):
                item_rect = item.mapToScene(item.boundingRect()).boundingRect()
                if not self.inner_rect.contains(item_rect):
                    faulty_items.append(item)
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

        try:
            painter = QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)
            self.render(painter, QRectF(0, 0, width_px, height_px), self.label_rect)
            painter.end()
        finally:
            for item in bound_items:
                item.set_export_record(None)
            for item in selected_items:
                item.setSelected(True)
            for overlay, was_visible in overlay_visibility:
                overlay.setVisible(was_visible)

        if not image.save(path, "PNG"):
            raise OSError(f"Unable to write PNG file: {path}")

    def finalize_and_save_template(self) -> str:
        """Sauvegarde le Gabarit en EXCLUANT les objets hors-limites."""
        faulty_items = self.validate_item_bounds()
        valid_data = []

        for item in self.items():
            if isinstance(item, BaseLabelItem) and item not in faulty_items:
                valid_data.append(item.to_dict())

        return self._serialize_items(valid_data)

    def _serialize_items(self, items: List[dict]) -> str:
        previous_items = self.template.items
        try:
            self.template.items = items
            return self.template.to_json()
        finally:
            self.template.items = previous_items
