"""Hiérarchie polymorphique des éléments du canvas et Fabrique d'objets (ItemFactory)."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Type
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QImage, QPen, QBrush, QColor, QFont, QPainterPath

from units import EDITOR_DPI, Length
from rich_text_models import Paragraph, CharFormat, VAlign, Overflow, SizingMode
from rich_layout import LayoutEngine, LayoutResult


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
        self.margins = (
            Length.from_pt(5, dpi=EDITOR_DPI),
            Length.from_pt(5, dpi=EDITOR_DPI),
            Length.from_pt(2.5, dpi=EDITOR_DPI),
            Length.from_pt(2.5, dpi=EDITOR_DPI),
        )
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
            pl.qlayout.draw(painter, QPointF(0, pl.y_top))
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


try:
    from qrcode.main import QRCode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

try:
    from barcode.codex import Code128
    from barcode.ean import EAN13
    HAS_BARCODE = True
except ImportError:
    HAS_BARCODE = False


class ImageItem(BaseItem):
    """Render an image source with caching and optional aspect preservation."""

    def __init__(self, rect: QRectF, source: Optional[str | bytes] = None, keep_aspect_ratio: bool = True, rotation: float = 0.0, z_index: int = 0):
        super().__init__(rect, rotation, z_index)
        self.source = source
        self.keep_aspect_ratio = keep_aspect_ratio
        self.opacity = 1.0
        self._cached_image: Optional[QImage] = None
        self._last_source: Optional[str | bytes] = None
        if source:
            self._load_image()

    def _load_image(self) -> None:
        if self.source == self._last_source and self._cached_image is not None:
            return
        self._last_source = self.source
        if isinstance(self.source, str):
            self._cached_image = QImage(self.source)
        elif isinstance(self.source, bytes):
            self._cached_image = QImage.fromData(self.source)
        else:
            self._cached_image = None

    def apply_data_binding(self, record: Dict[str, Any]) -> None:
        if self.binding_key and isinstance(record.get(self.binding_key), (str, bytes)):
            self.source = record[self.binding_key]
            self._load_image()

    def render(self, painter: QPainter, override_rect: Optional[QRectF] = None) -> None:
        target_rect = override_rect or self.rect
        painter.save()
        center = target_rect.center()
        painter.translate(center)
        painter.rotate(self.rotation)
        painter.translate(-center)
        painter.setOpacity(self.opacity)
        self._load_image()
        if self._cached_image and not self._cached_image.isNull():
            if self.keep_aspect_ratio:
                scaled = self._cached_image.scaled(target_rect.size().toSize(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                painter.drawImage(QPointF(target_rect.x() + (target_rect.width() - scaled.width()) / 2.0, target_rect.y() + (target_rect.height() - scaled.height()) / 2.0), scaled)
            else:
                painter.drawImage(target_rect, self._cached_image)
        else:
            painter.setPen(QPen(QColor("#a0a0a0"), 1.0, Qt.DashLine))
            painter.setBrush(QBrush(QColor("#f0f0f0")))
            painter.drawRect(target_rect)
            painter.setPen(QColor("#606060"))
            painter.drawText(target_rect, Qt.AlignCenter, "[ Image non disponible ]")
        painter.restore()


class QRCodeItem(BaseItem):
    """Render a QR code as vector rectangles."""

    def __init__(self, rect: QRectF, content: str = "https://example.com", module_color: str = "#000000", background_color: str = "#FFFFFF", rotation: float = 0.0, z_index: int = 0):
        super().__init__(rect, rotation, z_index)
        self.content = content
        self.module_color = module_color
        self.background_color = background_color

    def apply_data_binding(self, record: Dict[str, Any]) -> None:
        if self.binding_key and self.binding_key in record:
            self.content = str(record[self.binding_key])

    def render(self, painter: QPainter, override_rect: Optional[QRectF] = None) -> None:
        target_rect = override_rect or self.rect
        painter.save()
        center = target_rect.center()
        painter.translate(center)
        painter.rotate(self.rotation)
        painter.translate(-center)
        if self.background_color:
            painter.fillRect(target_rect, QColor(self.background_color))
        if HAS_QRCODE and self.content:
            qr = QRCode(border=1)
            qr.add_data(self.content)
            qr.make(fit=True)
            matrix = qr.get_matrix()
            rows = len(matrix)
            cols = len(matrix[0]) if rows else 0
            if rows and cols:
                cell_w = target_rect.width() / cols
                cell_h = target_rect.height() / rows
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor(self.module_color)))
                antialiasing = painter.renderHints()
                painter.setRenderHint(QPainter.Antialiasing, False)
                for row in range(rows):
                    for column in range(cols):
                        if matrix[row][column]:
                            left = round(target_rect.x() + column * cell_w)
                            top = round(target_rect.y() + row * cell_h)
                            right = round(target_rect.x() + (column + 1) * cell_w)
                            bottom = round(target_rect.y() + (row + 1) * cell_h)
                            painter.fillRect(QRectF(left, top, max(1, right - left), max(1, bottom - top)), QBrush(QColor(self.module_color)))
                painter.setRenderHints(antialiasing)
        else:
            painter.setPen(QPen(QColor(self.module_color), 1.0))
            painter.drawRect(target_rect)
            painter.drawText(target_rect, Qt.AlignCenter, "[ QR Code ]" if HAS_QRCODE else "[ install 'qrcode' ]")
        painter.restore()


class BarcodeItem(BaseItem):
    """Render Code 128 or EAN-13 barcodes as vector bars."""

    def __init__(self, rect: QRectF, code: str = "123456789012", barcode_type: str = "code128", show_text: bool = True, bar_color: str = "#000000", text_gap: float = 0.0, rotation: float = 0.0, z_index: int = 0):
        super().__init__(rect, rotation, z_index)
        self.code = code
        self.barcode_type = barcode_type.lower()
        self.show_text = show_text
        self.bar_color = bar_color
        self.text_gap = text_gap

    def apply_data_binding(self, record: Dict[str, Any]) -> None:
        if self.binding_key and self.binding_key in record:
            self.code = str(record[self.binding_key])

    def render(self, painter: QPainter, override_rect: Optional[QRectF] = None) -> None:
        target_rect = override_rect or self.rect
        painter.save()
        center = target_rect.center()
        painter.translate(center)
        painter.rotate(self.rotation)
        painter.translate(-center)
        if HAS_BARCODE and self.code:
            try:
                barcode = EAN13(self.code.zfill(12)[:12]) if self.barcode_type == "ean13" else Code128(self.code)
                pattern = barcode.build()[0]
                text_height = Length.from_pt(10, dpi=EDITOR_DPI) if self.show_text else 0.0
                bars_height = max(1.0, target_rect.height() - text_height - self.text_gap)
                module_width = target_rect.width() / len(pattern)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor(self.bar_color)))
                path = QPainterPath()
                for index, bit in enumerate(pattern):
                    if bit == "1":
                        path.addRect(QRectF(target_rect.x() + index * module_width, target_rect.y(), module_width + 0.05, bars_height))
                painter.drawPath(path)
                if self.show_text:
                    painter.setPen(QColor(self.bar_color))
                    font = QFont("Monospace")
                    font.setPointSizeF(8.0)
                    painter.setFont(font)
                    painter.drawText(QRectF(target_rect.x(), target_rect.y() + bars_height + self.text_gap, target_rect.width(), text_height), Qt.AlignCenter, self.code)
            except Exception as error:
                painter.setPen(QPen(QColor("#d32f2f"), 1.0))
                painter.drawRect(target_rect)
                painter.drawText(target_rect, Qt.AlignCenter, f"Code Erreur: {error}")
        else:
            painter.setPen(QPen(QColor(self.bar_color), 1.0, Qt.DashLine))
            painter.drawRect(target_rect)
            painter.drawText(target_rect, Qt.AlignCenter, f"[ Barcode: {self.code} ]" if HAS_BARCODE else "[ install 'python-barcode' ]")
        painter.restore()


class LineItem(BaseItem):
    """Render a horizontal line through the item rectangle."""

    def __init__(self, rect: QRectF, color: str = "#000000", thickness: float = 1.0, style: Qt.PenStyle = Qt.SolidLine, rotation: float = 0.0, z_index: int = 0):
        super().__init__(rect, rotation, z_index)
        self.color = color
        self.thickness = thickness
        self.style = style

    def render(self, painter: QPainter, override_rect: Optional[QRectF] = None) -> None:
        target_rect = override_rect or self.rect
        painter.save()
        center = target_rect.center()
        painter.translate(center)
        painter.rotate(self.rotation)
        painter.translate(-center)
        pen = QPen(QColor(self.color), self.thickness, self.style)
        pen.setCapStyle(Qt.SquareCap)
        painter.setPen(pen)
        y_center = target_rect.y() + target_rect.height() / 2.0
        painter.drawLine(QPointF(target_rect.left(), y_center), QPointF(target_rect.right(), y_center))
        painter.restore()


class EllipseItem(BaseItem):
    """Render an ellipse with configurable fill and border."""

    def __init__(self, rect: QRectF, fill_color: str = "#FFFFFF", border_color: str = "#000000", border_width: float = 1.0, rotation: float = 0.0, z_index: int = 0):
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
        painter.setPen(QPen(QColor(self.border_color), self.border_width) if self.border_width > 0 else Qt.NoPen)
        painter.setBrush(QBrush(QColor(self.fill_color)) if self.fill_color else Qt.NoBrush)
        painter.drawEllipse(target_rect)
        painter.restore()


for _type_name, _item_class in {
    "image": ImageItem,
    "qrcode": QRCodeItem,
    "barcode": BarcodeItem,
    "line": LineItem,
    "ellipse": EllipseItem,
}.items():
    ItemFactory.register(_type_name, _item_class)
