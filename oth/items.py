"""Hiérarchie polymorphique des éléments du canvas et Fabrique d'objets (ItemFactory)."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Type
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor

from units import Length
from models import Paragraph, CharFormat, VAlign, Overflow, SizingMode
from layout import LayoutEngine, LayoutResult


class BaseItem(ABC):
    """Classe de base polymorphique pour tous les éléments du canvas."""

    def __init__(self, rect: QRectF, rotation: float = 0.0, z_index: int = 0):
        self.rect: QRectF = QRectF(rect)
        self.rotation: float = rotation
        self.z_index: int = z_index
        self.locked: bool = False
        self.binding_key: Optional[str] = None

    @abstractmethod
    def render(self, painter: QPainter, override_rect: Optional[QRectF] = None) -> None:
        pass

    def apply_data_binding(self, record: Dict[str, Any]) -> None:
        pass


class ShapeItem(BaseItem):
    """Élément géométrique (Rectangle)."""

    def __init__(
        self,
        rect: QRectF,
        fill_color: str = "#FFFFFF",
        border_color: str = "#000000",
        border_width: float = 1.0,
        rotation: float = 0.0,
        z_index: int = 0
    ):
        super().__init__(rect, rotation, z_index)
        self.fill_color = fill_color
        self.border_color = border_color
        self.border_width = border_width

    def render(self, painter: QPainter, override_rect: Optional[QRectF] = None) -> None:
        target_rect = override_rect or self.rect
        painter.save()

        center = target_rect.center()
        painter.translate(center)
        painter.rotate(self.rotation)
        painter.translate(-center)

        painter.setPen(QPen(QColor(self.border_color), self.border_width))
        painter.setBrush(QBrush(QColor(self.fill_color)))
        painter.drawRect(target_rect)
        painter.restore()


class TextItem(BaseItem):
    """Zone de texte complexe multi-paragraphes."""

    def __init__(
        self,
        rect: QRectF,
        paragraphs: Optional[List[Paragraph]] = None,
        rotation: float = 0.0,
        z_index: int = 0
    ):
        super().__init__(rect, rotation, z_index)
        self.paragraphs: List[Paragraph] = paragraphs or [Paragraph()]
        # Utilisation de Length (Value Object) pour les marges
        self.margins = (Length.from_pt(5), Length.from_pt(5), Length.from_pt(2.5), Length.from_pt(2.5))
        self.valign: VAlign = VAlign.TOP
        self.overflow: Overflow = Overflow.AUTOFIT_SHRINK
        self.wrap: bool = True
        self.sizing_mode: SizingMode = SizingMode.FREE_RESIZE
        self.placeholder: str = ""

        self.fill_color: Optional[str] = None
        self.fill_opacity: int = 255
        self.border_color: str = "#cccccc"
        self.border_width: float = 0.0
        self.border_style = Qt.SolidLine
        self.corner_radius: float = 0.0

        self.font_scale: float = 1.0
        self.line_spacing_reduction: float = 0.0
        self.engine = LayoutEngine()

    def plain_text(self) -> str:
        return "\n".join(p.text for p in self.paragraphs)

    def set_text(self, text: str, default_format: Optional[CharFormat] = None) -> None:
        self.paragraphs = [Paragraph(text, default_format=default_format)]

    def apply_data_binding(self, record: Dict[str, Any]) -> None:
        if self.binding_key and self.binding_key in record:
            self.set_text(str(record[self.binding_key]))

    def content_rect_for(self, target_rect: QRectF) -> QRectF:
        l, r, t, b = self.margins
        return target_rect.adjusted(l, t, -r, -b)

    def render(self, painter: QPainter, override_rect: Optional[QRectF] = None) -> None:
        target_rect = override_rect or self.rect
        painter.save()

        center = target_rect.center()
        painter.translate(center)
        painter.rotate(self.rotation)
        painter.translate(-center)

        if self.fill_color:
            fill = QColor(self.fill_color)
            fill.setAlpha(max(0, min(255, self.fill_opacity)))
            painter.fillRect(target_rect, fill)

        if self.border_width > 0:
            painter.setPen(QPen(QColor(self.border_color), self.border_width, self.border_style))
            painter.setBrush(Qt.NoBrush)
            if self.corner_radius > 0:
                painter.drawRoundedRect(target_rect, self.corner_radius, self.corner_radius)
            else:
                painter.drawRect(target_rect)

        content = self.content_rect_for(target_rect)
        layout_result = self.engine.layout(self, content)
        v_offset = self._vertical_offset(layout_result, content)

        if self.overflow == Overflow.CLIP:
            painter.setClipRect(target_rect)

        painter.save()
        painter.translate(content.left(), content.top() + v_offset)
        for pl in layout_result.paragraph_layouts:
            pl.qlayout.draw(painter, Qt.PointF(0, pl.y_top))
        painter.restore()

        if not self.plain_text() and self.placeholder:
            painter.setPen(QColor("#888888"))
            painter.drawText(content, Qt.AlignLeft | Qt.AlignTop, self.placeholder)

        painter.restore()

    def _vertical_offset(self, result: LayoutResult, content: QRectF) -> float:
        if self.overflow == Overflow.AUTOFIT_SHRINK:
            return 0.0
        if self.valign == VAlign.MIDDLE:
            return max(0.0, (content.height() - result.total_height) / 2)
        if self.valign == VAlign.BOTTOM:
            return max(0.0, content.height() - result.total_height)
        return 0.0


class ItemFactory:
    """Fabrique dynamique d'éléments (Pattern inspiré de python-pptx ShapeFactory)."""

    _registry: Dict[str, Type[BaseItem]] = {}

    @classmethod
    def register(cls, type_name: str, item_cls: Type[BaseItem]) -> None:
        cls._registry[type_name] = item_cls

    @classmethod
    def create(cls, type_name: str, **kwargs) -> BaseItem:
        if type_name not in cls._registry:
            raise ValueError(f"Type d'élément inconnu: '{type_name}'")
        return cls._registry[type_name](**kwargs)


# Enregistrement automatique des types de base
ItemFactory.register("shape", ShapeItem)
ItemFactory.register("text", TextItem)