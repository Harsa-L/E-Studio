"""Éléments graphiques positionnables sur le Canvas et bande d'avertissement clignotante."""

from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict
from typing import List, Dict, Any
from PySide6.QtCore import QRectF, Qt, Signal, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtWidgets import QGraphicsObject, QGraphicsItem, QGraphicsRectItem

from item_properties import PropertySpec
from tier_engine import CancelLabelGenerationException, TierResolver, TierTargetSpec
from render_items import BarcodeItem, BaseItem, EllipseItem, ImageItem, LineItem, QRCodeItem, ShapeItem, TextItem
from rich_text_models import CharFormat, Paragraph, ParagraphFormat, TextAlignment, VAlign, Overflow


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
        if item_type == "RichLabelItem":
            return RichLabelItem.from_dict(data, scale_px_per_mm)
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
        self._export_record: Dict[str, Any] | None = None

    def paint(self, painter: QPainter, option, widget=None):
        painter.save()
        rect = self.boundingRect()
        
        painter.setBrush(QBrush(QColor("#E3F2FD")))
        painter.setPen(QPen(QColor("#1976D2"), 2 if self.isSelected() else 1))
        painter.drawRoundedRect(rect, 4, 4)

        painter.setPen(QPen(QColor("#0D47A1")))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        label = self._display_text()
        painter.drawText(rect.adjusted(5, 2, -5, -2), Qt.AlignVCenter | Qt.AlignLeft, label)
        painter.restore()

    def _display_text(self) -> str:
        if self._export_record is not None:
            spec = TierTargetSpec(
                primary_index=max(0, self.primary_tier - 1),
                strict_required=self.strict_required,
                keyword_prefix=self.prefix_text,
                unit_label=self.unit_label,
            )
            try:
                resolved = TierResolver.resolve(spec, self._export_record)
            except CancelLabelGenerationException:
                return "[Palier requis indisponible]"
            if resolved:
                suffix = " (repli)" if resolved["is_fallback"] else ""
                return f"{resolved['text_qty']} — {resolved['formatted_price']}{suffix}"
        label = f"[{self.prefix_text}] Palier #{self.primary_tier} ({self.unit_label})"
        return f"{label} *" if self.strict_required else label

    def set_export_record(self, record: Dict[str, Any] | None) -> None:
        self._export_record = record
        self.update()

    def get_tier(self) -> int: return self.primary_tier
    def set_tier(self, val: int):
        self.primary_tier = val
        self.update()
        self.item_changed.emit()

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


class RichLabelItem(BaseLabelItem):
    """Editable scene-item wrapper around reusable rendering primitives."""

    TYPE = "RichLabelItem"
    SUPPORTED_TYPES = {"text", "shape", "image", "qrcode", "barcode", "line", "ellipse"}

    def __init__(
        self,
        item_id: str,
        rich_type: str,
        x_mm: float,
        y_mm: float,
        w_mm: float,
        h_mm: float,
        scale_px_per_mm: float = BaseLabelItem.SCALE_PX_PER_MM,
        rich_item: BaseItem | None = None,
    ):
        if rich_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"Unsupported rich item type: {rich_type!r}")
        self.rich_type = rich_type
        self.rich_item = rich_item
        self._export_record: Dict[str, Any] | None = None
        super().__init__(item_id, x_mm, y_mm, w_mm, h_mm, scale_px_per_mm)
        if self.rich_item is None:
            self.rich_item = self._make_rich_item()
        self._sync_rich_rect()

    @classmethod
    def create(
        cls,
        rich_type: str,
        item_id: str,
        x_mm: float = 10.0,
        y_mm: float = 10.0,
        w_mm: float | None = None,
        h_mm: float | None = None,
        scale_px_per_mm: float = BaseLabelItem.SCALE_PX_PER_MM,
    ) -> "RichLabelItem":
        defaults = {
            "text": (60.0, 18.0), "shape": (40.0, 25.0), "image": (40.0, 30.0),
            "qrcode": (28.0, 28.0), "barcode": (55.0, 22.0), "line": (60.0, 2.0),
            "ellipse": (35.0, 25.0),
        }
        if rich_type not in defaults:
            raise ValueError(f"Unsupported rich item type: {rich_type!r}")
        default_w, default_h = defaults[rich_type]
        return cls(item_id, rich_type, x_mm, y_mm, w_mm or default_w, h_mm or default_h, scale_px_per_mm)

    def _make_rich_item(self) -> BaseItem:
        rect = QRectF(self.boundingRect())
        if self.rich_type == "text":
            return TextItem(rect, [Paragraph("Texte", CharFormat(font_size=14.0))])
        if self.rich_type == "shape":
            return ShapeItem(rect, fill_color="#FFFFFF", border_color="#263238")
        if self.rich_type == "image":
            return ImageItem(rect)
        if self.rich_type == "qrcode":
            return QRCodeItem(rect, content="https://example.com")
        if self.rich_type == "barcode":
            return BarcodeItem(rect, code="123456789012", barcode_type="code128")
        if self.rich_type == "line":
            return LineItem(rect, color="#263238", thickness=1.5)
        return EllipseItem(rect, fill_color="#FFFFFF", border_color="#263238")

    def _sync_rich_rect(self) -> None:
        self.rich_item.rect = QRectF(self.boundingRect())

    def set_w_mm(self, val: float) -> None:
        super().set_w_mm(val)
        self._sync_rich_rect()

    def set_h_mm(self, val: float) -> None:
        super().set_h_mm(val)
        self._sync_rich_rect()

    def paint(self, painter: QPainter, option, widget=None) -> None:
        rich_item = self.rich_item
        if self._export_record is not None and rich_item.binding_key:
            rich_item = deepcopy(rich_item)
            rich_item.apply_data_binding(self._export_record)
        rich_item.render(painter, self.boundingRect())
        if self.isSelected():
            painter.setPen(QPen(QColor("#1976D2"), 1.5))
            painter.setBrush(QBrush())
            painter.drawRect(self.boundingRect())

    def set_export_record(self, record: Dict[str, Any] | None) -> None:
        self._export_record = record
        self.update()

    def _changed(self) -> None:
        self.update()
        self.item_changed.emit()

    def _get_binding_key(self) -> str:
        return self.rich_item.binding_key or ""

    def _set_binding_key(self, value: str) -> None:
        self.rich_item.binding_key = value.strip() or None
        self._changed()

    def _get_rotation(self) -> float:
        return self.rich_item.rotation

    def _set_rotation(self, value: float) -> None:
        self.rich_item.rotation = float(value)
        self._changed()

    def _get_z_index(self) -> int:
        return self.rich_item.z_index

    def _set_z_index(self, value: int) -> None:
        self.rich_item.z_index = int(value)
        self.setZValue(self.rich_item.z_index)
        self._changed()

    def _get_text(self) -> str:
        return self.rich_item.plain_text()  # type: ignore[union-attr]

    def _set_text(self, value: str) -> None:
        self.rich_item.set_text(value)  # type: ignore[union-attr]
        self._changed()

    def _get_font_size(self) -> float:
        text_item: TextItem = self.rich_item  # type: ignore[assignment]
        for paragraph in text_item.paragraphs:
            if paragraph.runs:
                return paragraph.runs[0].format.font_size
        return 18.0

    def _set_font_size(self, value: float) -> None:
        text_item: TextItem = self.rich_item  # type: ignore[assignment]
        for paragraph in text_item.paragraphs:
            paragraph.set_format(0, len(paragraph), font_size=float(value))
        self._changed()

    def _get_attr(self, name: str) -> Any:
        return getattr(self.rich_item, name)

    def _set_attr(self, name: str, value: Any) -> None:
        setattr(self.rich_item, name, value)
        self._changed()

    def get_properties(self) -> List[PropertySpec]:
        props = super().get_properties()
        props.extend([
            PropertySpec("binding_key", "Clé de données", "str", "Données", self._get_binding_key, self._set_binding_key),
            PropertySpec("rotation", "Rotation", "float", "Apparence", self._get_rotation, self._set_rotation, -360, 360, " °"),
            PropertySpec("z_index", "Plan", "int", "Apparence", self._get_z_index, self._set_z_index, -100, 100),
        ])
        if self.rich_type == "text":
            props.extend([
                PropertySpec("text", "Texte", "str", "Texte", self._get_text, self._set_text),
                PropertySpec("font_size", "Taille", "float", "Texte", self._get_font_size, self._set_font_size, 1, 200, " pt"),
            ])
        elif self.rich_type in {"shape", "ellipse"}:
            props.extend([
                PropertySpec("fill_color", "Couleur de fond", "str", "Apparence", lambda: self._get_attr("fill_color"), lambda v: self._set_attr("fill_color", v)),
                PropertySpec("border_color", "Couleur du trait", "str", "Apparence", lambda: self._get_attr("border_color"), lambda v: self._set_attr("border_color", v)),
                PropertySpec("border_width", "Épaisseur", "float", "Apparence", lambda: self._get_attr("border_width"), lambda v: self._set_attr("border_width", float(v)), 0, 50, " px"),
            ])
        elif self.rich_type == "image":
            props.extend([
                PropertySpec("source", "Fichier image", "str", "Image", lambda: self._get_attr("source") or "", lambda v: self._set_attr("source", v or None)),
                PropertySpec("keep_aspect_ratio", "Conserver ratio", "bool", "Image", lambda: self._get_attr("keep_aspect_ratio"), lambda v: self._set_attr("keep_aspect_ratio", bool(v))),
                PropertySpec("opacity", "Opacité", "float", "Image", lambda: self._get_attr("opacity"), lambda v: self._set_attr("opacity", max(0.0, min(1.0, float(v)))), 0, 1),
            ])
        elif self.rich_type == "qrcode":
            props.extend([
                PropertySpec("content", "Contenu", "str", "QR code", lambda: self._get_attr("content"), lambda v: self._set_attr("content", v)),
                PropertySpec("module_color", "Couleur modules", "str", "QR code", lambda: self._get_attr("module_color"), lambda v: self._set_attr("module_color", v)),
                PropertySpec("background_color", "Couleur fond", "str", "QR code", lambda: self._get_attr("background_color"), lambda v: self._set_attr("background_color", v)),
            ])
        elif self.rich_type == "barcode":
            props.extend([
                PropertySpec("code", "Code", "str", "Code-barres", lambda: self._get_attr("code"), lambda v: self._set_attr("code", v)),
                PropertySpec("barcode_type", "Type", "str", "Code-barres", lambda: self._get_attr("barcode_type"), lambda v: self._set_attr("barcode_type", v.lower())),
                PropertySpec("show_text", "Afficher texte", "bool", "Code-barres", lambda: self._get_attr("show_text"), lambda v: self._set_attr("show_text", bool(v))),
                PropertySpec("bar_color", "Couleur", "str", "Code-barres", lambda: self._get_attr("bar_color"), lambda v: self._set_attr("bar_color", v)),
            ])
        elif self.rich_type == "line":
            props.extend([
                PropertySpec("color", "Couleur", "str", "Ligne", lambda: self._get_attr("color"), lambda v: self._set_attr("color", v)),
                PropertySpec("thickness", "Épaisseur", "float", "Ligne", lambda: self._get_attr("thickness"), lambda v: self._set_attr("thickness", float(v)), 0.1, 50, " px"),
            ])
        return props

    def _rich_properties(self) -> Dict[str, Any]:
        item = self.rich_item
        data: Dict[str, Any] = {"binding_key": item.binding_key, "rotation": item.rotation, "z_index": item.z_index}
        if self.rich_type == "text":
            text_item: TextItem = item  # type: ignore[assignment]
            data.update({
                "paragraphs": [
                    {
                        "runs": [{"text": run.text, "format": asdict(run.format)} for run in paragraph.runs],
                        "format": {**asdict(paragraph.pformat), "alignment": paragraph.pformat.alignment.value},
                    }
                    for paragraph in text_item.paragraphs
                ],
                "fill_color": text_item.fill_color,
                "fill_opacity": text_item.fill_opacity,
                "border_color": text_item.border_color,
                "border_width": text_item.border_width,
                "corner_radius": text_item.corner_radius,
                "valign": text_item.valign.name,
                "overflow": text_item.overflow.name,
                "wrap": text_item.wrap,
                "placeholder": text_item.placeholder,
            })
        elif self.rich_type in {"shape", "ellipse"}:
            data.update(fill_color=item.fill_color, border_color=item.border_color, border_width=item.border_width)
        elif self.rich_type == "image":
            data.update(source=item.source if isinstance(item.source, str) else None, keep_aspect_ratio=item.keep_aspect_ratio, opacity=item.opacity)
        elif self.rich_type == "qrcode":
            data.update(content=item.content, module_color=item.module_color, background_color=item.background_color)
        elif self.rich_type == "barcode":
            data.update(code=item.code, barcode_type=item.barcode_type, show_text=item.show_text, bar_color=item.bar_color)
        elif self.rich_type == "line":
            data.update(color=item.color, thickness=item.thickness)
        return data

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({"type": self.TYPE, "rich_type": self.rich_type, "rich_properties": self._rich_properties()})
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any], scale_px_per_mm: float = BaseLabelItem.SCALE_PX_PER_MM) -> "RichLabelItem":
        rich_type = data["rich_type"]
        item = cls(data["id"], rich_type, data["x_mm"], data["y_mm"], data["w_mm"], data["h_mm"], scale_px_per_mm)
        props = data.get("rich_properties", {})
        rich = item.rich_item
        rich.binding_key = props.get("binding_key") or None
        rich.rotation = float(props.get("rotation", 0.0))
        rich.z_index = int(props.get("z_index", 0))
        item.setZValue(rich.z_index)
        if rich_type == "text":
            if props.get("paragraphs"):
                paragraphs = []
                from rich_text_models import Run
                for saved in props["paragraphs"]:
                    pf_data = dict(saved.get("format", {}))
                    pf_data["alignment"] = TextAlignment(pf_data.get("alignment", TextAlignment.LEFT.value))
                    paragraph = Paragraph(pformat=ParagraphFormat(**pf_data))
                    paragraph.runs = [Run(str(run.get("text", "")), CharFormat(**run.get("format", {}))) for run in saved.get("runs", [])]
                    paragraphs.append(paragraph)
                rich.paragraphs = paragraphs or [Paragraph()]
            for attr in ("fill_color", "fill_opacity", "border_color", "border_width", "corner_radius", "wrap", "placeholder"):
                if attr in props:
                    setattr(rich, attr, props[attr])
            rich.valign = VAlign[props.get("valign", "TOP")]
            rich.overflow = Overflow[props.get("overflow", "AUTOFIT_SHRINK")]
        elif rich_type in {"shape", "ellipse"}:
            for attr in ("fill_color", "border_color", "border_width"):
                if attr in props:
                    setattr(rich, attr, props[attr])
        elif rich_type == "image":
            for attr in ("source", "keep_aspect_ratio", "opacity"):
                if attr in props:
                    setattr(rich, attr, props[attr])
        elif rich_type == "qrcode":
            for attr in ("content", "module_color", "background_color"):
                if attr in props:
                    setattr(rich, attr, props[attr])
        elif rich_type == "barcode":
            for attr in ("code", "barcode_type", "show_text", "bar_color"):
                if attr in props:
                    setattr(rich, attr, props[attr])
        elif rich_type == "line":
            for attr in ("color", "thickness"):
                if attr in props:
                    setattr(rich, attr, props[attr])
        item._sync_rich_rect()
        return item
