"""Éléments graphiques positionnables sur le Canvas et bande d'avertissement clignotante."""

from __future__ import annotations
from typing import List, Dict, Any
from PySide6.QtCore import QRectF, Qt, Signal, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtWidgets import QGraphicsObject, QGraphicsItem, QGraphicsRectItem

from item_properties import PropertySpec


class HazardWarningOverlay(QGraphicsRectItem):
    """Bande clignotante rouge/blanc inclinée signalant un débordement."""

    def __init__(self, rect: QRectF):
        super().__init__(rect)
        self.setZValue(999)
        self.is_phase_a = True
        self.setPen(QPen(Qt.NoPen))

        self.timer = QTimer()
        self.timer.timeout.connect(self.toggle_phase)
        self.timer.start(500)

    def toggle_phase(self):
        self.is_phase_a = not self.is_phase_a
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        painter.save()
        color1 = QColor(220, 20, 60, 200) if self.is_phase_a else QColor(255, 255, 255, 200)
        
        brush = QBrush(Qt.BDiagPattern)
        brush.setColor(color1)

        painter.fillRect(self.rect(), QColor(255, 0, 0, 50))
        painter.fillRect(self.rect(), brush)
        painter.setPen(QPen(QColor(180, 0, 0), 2, Qt.DashLine))
        painter.drawRect(self.rect())
        painter.restore()


class BaseLabelItem(QGraphicsObject):
    """Objet de base interactif positionnable en mm."""

    item_changed = Signal()
    SCALE_PX_PER_MM = 3.78

    def __init__(self, item_id: str, x_mm: float, y_mm: float, w_mm: float, h_mm: float,
                 scale_px_per_mm: float = SCALE_PX_PER_MM):
        super().__init__()
        self.item_id = item_id
        self.scale_px_per_mm = scale_px_per_mm
        self._rect = QRectF(0, 0, w_mm * self.scale_px_per_mm, h_mm * self.scale_px_per_mm)
        self.setPos(x_mm * self.scale_px_per_mm, y_mm * self.scale_px_per_mm)

        self.setFlags(
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemSendsGeometryChanges
        )

    def boundingRect(self) -> QRectF:
        return self._rect

    def paint(self, painter: QPainter, option, widget=None):
        painter.setPen(QPen(QColor("#616161")))
        painter.setBrush(QBrush(QColor("#eeeeee")))
        painter.drawRect(self.boundingRect())

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change in (QGraphicsItem.ItemPositionHasChanged, QGraphicsItem.ItemTransformHasChanged):
            self.item_changed.emit()
        return super().itemChange(change, value)

    def get_x_mm(self) -> float: return round(self.pos().x() / self.scale_px_per_mm, 2)
    def set_x_mm(self, val: float):
        self.setPos(val * self.scale_px_per_mm, self.pos().y())
        self.update()
        self.item_changed.emit()

    def get_y_mm(self) -> float: return round(self.pos().y() / self.scale_px_per_mm, 2)
    def set_y_mm(self, val: float):
        self.setPos(self.pos().x(), val * self.scale_px_per_mm)
        self.update()
        self.item_changed.emit()

    def get_w_mm(self) -> float: return round(self._rect.width() / self.scale_px_per_mm, 2)
    def set_w_mm(self, val: float):
        self.prepareGeometryChange()
        self._rect.setWidth(val * self.scale_px_per_mm)
        self.update()
        self.item_changed.emit()

    def get_h_mm(self) -> float: return round(self._rect.height() / self.scale_px_per_mm, 2)
    def set_h_mm(self, val: float):
        self.prepareGeometryChange()
        self._rect.setHeight(val * self.scale_px_per_mm)
        self.update()
        self.item_changed.emit()

    def get_properties(self) -> List[PropertySpec]:
        return [
            PropertySpec("x_mm", "Position X", "float", "Géométrie", self.get_x_mm, self.set_x_mm, 0, 500, " mm"),
            PropertySpec("y_mm", "Position Y", "float", "Géométrie", self.get_y_mm, self.set_y_mm, 0, 500, " mm"),
            PropertySpec("w_mm", "Largeur", "float", "Géométrie", self.get_w_mm, self.set_w_mm, 1, 500, " mm"),
            PropertySpec("h_mm", "Hauteur", "float", "Géométrie", self.get_h_mm, self.set_h_mm, 1, 500, " mm"),
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.item_id,
            "type": self.__class__.__name__,
            "x_mm": self.get_x_mm(),
            "y_mm": self.get_y_mm(),
            "w_mm": self.get_w_mm(),
            "h_mm": self.get_h_mm()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], scale_px_per_mm: float = SCALE_PX_PER_MM) -> "BaseLabelItem":
        item_type = data.get("type")
        if item_type == "TierPriceLabelItem":
            item_class = TierPriceLabelItem
        elif item_type == "BaseLabelItem":
            item_class = cls
        else:
            raise ValueError(f"Unsupported item type: {item_type!r}")
        item = item_class(data["id"], data["x_mm"], data["y_mm"], data["w_mm"],
                          data["h_mm"], scale_px_per_mm=scale_px_per_mm)
        if isinstance(item, TierPriceLabelItem):
            item.primary_tier = int(data.get("primary_tier", item.primary_tier))
            item.prefix_text = data.get("prefix_text", item.prefix_text)
            item.unit_label = data.get("unit_label", item.unit_label)
            item.strict_required = bool(data.get("strict_required", item.strict_required))
        return item


class TierPriceLabelItem(BaseLabelItem):
    """Objet spécifique au Palier de Prix Cash&Carry."""

    def __init__(self, item_id: str, x_mm: float, y_mm: float, w_mm: float = 60.0,
                 h_mm: float = 15.0, scale_px_per_mm: float = BaseLabelItem.SCALE_PX_PER_MM):
        super().__init__(item_id, x_mm, y_mm, w_mm, h_mm, scale_px_per_mm)
        self.primary_tier: int = 1
        self.prefix_text: str = "À partir de"
        self.unit_label: str = "FCFA"
        self.strict_required: bool = False

    def paint(self, painter: QPainter, option, widget=None):
        painter.save()
        rect = self.boundingRect()
        
        painter.setBrush(QBrush(QColor("#E3F2FD")))
        painter.setPen(QPen(QColor("#1976D2"), 2 if self.isSelected() else 1))
        painter.drawRoundedRect(rect, 4, 4)

        painter.setPen(QPen(QColor("#0D47A1")))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        label = f"[{self.prefix_text}] Palier #{self.primary_tier} ({self.unit_label})"
        if self.strict_required: label += " *"
        painter.drawText(rect.adjusted(5, 2, -5, -2), Qt.AlignVCenter | Qt.AlignLeft, label)
        painter.restore()

    def get_tier(self) -> int: return self.primary_tier
    def set_tier(self, val: int):
        self.primary_tier = val
        self.update()
        self.item_changed.emit()

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "primary_tier": self.primary_tier,
            "prefix_text": self.prefix_text,
            "unit_label": self.unit_label,
            "strict_required": self.strict_required,
        })
        return data

    def get_prefix(self) -> str: return self.prefix_text
    def set_prefix(self, val: str):
        self.prefix_text = val
        self.update()
        self.item_changed.emit()

    def get_unit(self) -> str: return self.unit_label
    def set_unit(self, val: str):
        self.unit_label = val
        self.update()
        self.item_changed.emit()

    def get_strict(self) -> bool: return self.strict_required
    def set_strict(self, val: bool):
        self.strict_required = val
        self.update()
        self.item_changed.emit()

    def get_properties(self) -> List[PropertySpec]:
        props = super().get_properties()
        props.extend([
            PropertySpec("tier_idx", "Palier Cible", "int", "Paliers Cash&Carry", self.get_tier, self.set_tier, 1, 10),
            PropertySpec("prefix", "Préfixe", "str", "Paliers Cash&Carry", self.get_prefix, self.set_prefix),
            PropertySpec("unit", "Unité/Devise", "str", "Paliers Cash&Carry", self.get_unit, self.set_unit),
            PropertySpec("strict", "Obligatoire", "bool", "Paliers Cash&Carry", self.get_strict, self.set_strict),
        ])
        return props

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "primary_tier": self.primary_tier,
            "prefix_text": self.prefix_text,
            "unit_label": self.unit_label,
            "strict_required": self.strict_required
        })
        return data