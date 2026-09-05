"""Générateur d'impression hors-écran haute performance."""

from __future__ import annotations
from copy import deepcopy
from typing import List, Dict, Any
from PySide6.QtCore import Qt, QSizeF
from PySide6.QtGui import QPainter, QImage

from render_items import BaseItem


class BatchRenderer:
    """Génère les rendus d'étiquettes haute définition en masse sans IHM."""

    @staticmethod
    def render_label_to_image(
        items: List[BaseItem],
        data_record: Dict[str, Any],
        label_size_px: QSizeF,
        dpi: float = 300.0
    ) -> QImage:
        image = QImage(int(label_size_px.width()), int(label_size_px.height()), QImage.Format_ARGB32_Premultiplied)
        image.setDotsPerMeterX(int(dpi / 0.0254))
        image.setDotsPerMeterY(int(dpi / 0.0254))
        image.fill(Qt.white)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        sorted_items = sorted(items, key=lambda x: x.z_index)
        for item in sorted_items:
            item_copy = deepcopy(item)
            item_copy.apply_data_binding(data_record)
            item_copy.render(painter)

        painter.end()
        return image
