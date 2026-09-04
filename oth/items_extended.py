"""Composants graphiques complémentaires pour l'éditeur d'étiquettes et le générateur vectoriel.

Incorpore :
- ImageItem (Chargement, cache et redimensionnement d'images)
- QRCodeItem (Génération vectorielle temps réel de QR codes)
- BarcodeItem (Génération vectorielle EAN-13, Code 128, etc.)
- LineItem & EllipseItem (Formes géométriques complémentaires)
"""

from __future__ import annotations
import io
from typing import Optional, Dict, Any, List
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QImage, QPixmap, QColor, QPen, QBrush, QFont, QPainterPath

from .items import BaseItem, ItemFactory
from .units import Length

# Chargement conditionnel des bibliothèques externes pour éviter un crash si non installées
try:
    import qrcode
    from qrcode.main import QRCode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

try:
    import barcode
    from barcode.codex import Code128
    from barcode.ean import EAN13
    HAS_BARCODE = True
except ImportError:
    HAS_BARCODE = False


class ImageItem(BaseItem):
    """Élément d'image prenant en charge le stockage local, le cache et l'ajustement du ratio."""

    def __init__(
        self,
        rect: QRectF,
        source: Optional[str | bytes] = None,
        keep_aspect_ratio: bool = True,
        rotation: float = 0.0,
        z_index: int = 0
    ):
        super().__init__(rect, rotation, z_index)
        self.source: Optional[str | bytes] = source
        self.keep_aspect_ratio: bool = keep_aspect_ratio
        self.opacity: float = 1.0
        self._cached_image: Optional[QImage] = None
        self._last_source: Optional[str | bytes] = None

        if source:
            self._load_image()

    def _load_image(self) -> None:
        """Charge l'image en mémoire tampon (évite les E/S disque répétées lors du rendu)."""
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
        """Injecte un chemin d'accès ou des octets d'image depuis les données métier."""
        if self.binding_key and self.binding_key in record:
            val = record[self.binding_key]
            if isinstance(val, (str, bytes)):
                self.source = val
                self._load_image()

    def render(self, painter: QPainter, override_rect: Optional[QRectF] = None) -> None:
        target_rect = override_rect or self.rect
        painter.save()

        # Application de la transformation spatiale (rotation autour du centre)
        center = target_rect.center()
        painter.translate(center)
        painter.rotate(self.rotation)
        painter.translate(-center)

        painter.setOpacity(self.opacity)
        self._load_image()

        if self._cached_image and not self._cached_image.isNull():
            if self.keep_aspect_ratio:
                scaled = self._cached_image.scaled(
                    target_rect.size().toSize(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                # Centrage de l'image ajustée dans le rectangle cible
                x_off = target_rect.x() + (target_rect.width() - scaled.width()) / 2.0
                y_off = target_rect.y() + (target_rect.height() - scaled.height()) / 2.0
                painter.drawImage(QPointF(x_off, y_off), scaled)
            else:
                painter.drawImage(target_rect, self._cached_image)
        else:
            # Fallback visuel si l'image est manquante ou invalide
            painter.setPen(QPen(QColor("#a0a0a0"), 1.0, Qt.DashLine))
            painter.setBrush(QBrush(QColor("#f0f0f0")))
            painter.drawRect(target_rect)
            painter.setPen(QColor("#606060"))
            painter.drawText(target_rect, Qt.AlignCenter, "[ Image non disponible ]")

        painter.restore()


class QRCodeItem(BaseItem):
    """Générateur vectoriel de QR Code pixel-perfect (sans flou de rastérisation)."""

    def __init__(
        self,
        rect: QRectF,
        content: str = "https://example.com",
        module_color: str = "#000000",
        background_color: str = "#FFFFFF",
        rotation: float = 0.0,
        z_index: int = 0
    ):
        super().__init__(rect, rotation, z_index)
        self.content: str = content
        self.module_color: str = module_color
        self.background_color: str = background_color

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

        # Fond du QR Code
        if self.background_color:
            painter.fillRect(target_rect, QColor(self.background_color))

        if HAS_QRCODE and self.content:
            qr = QRCode(border=1)
            qr.add_data(self.content)
            qr.make(fit=True)
            matrix = qr.get_matrix()

            rows = len(matrix)
            cols = len(matrix[0]) if rows > 0 else 0

            if rows > 0 and cols > 0:
                cell_w = target_rect.width() / cols
                cell_h = target_rect.height() / rows

                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor(self.module_color)))

                # Rendu vectoriel sous forme de chemin unifié (Haute performance)
                path = QPainterPath()
                for r in range(rows):
                    for c in range(cols):
                        if matrix[r][c]:
                            x = target_rect.x() + c * cell_w
                            y = target_rect.y() + r * cell_h
                            path.addRect(QRectF(x, y, cell_w + 0.1, cell_h + 0.1)) # +0.1 évite les artefacts d'interstice
                painter.drawPath(path)
        else:
            # Fallback si le module 'qrcode' n'est pas présent dans l'environnement
            painter.setPen(QPen(QColor(self.module_color), 1.0))
            painter.drawRect(target_rect)
            msg = "[ QR Code ]" if HAS_QRCODE else "[ install 'qrcode' ]"
            painter.drawText(target_rect, Qt.AlignCenter, msg)

        painter.restore()


class BarcodeItem(BaseItem):
    """Élément Code-barres vectoriel (EAN-13, Code128) avec libellé numérique sous-jacent."""

    def __init__(
        self,
        rect: QRectF,
        code: str = "123456789012",
        barcode_type: str = "code128",
        show_text: bool = True,
        bar_color: str = "#000000",
        rotation: float = 0.0,
        z_index: int = 0
    ):
        super().__init__(rect, rotation, z_index)
        self.code: str = code
        self.barcode_type: str = barcode_type.lower()
        self.show_text: bool = show_text
        self.bar_color: str = bar_color

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
                # Génération des modules du code-barres sous forme de matrice binaire
                if self.barcode_type == "ean13":
                    # Ajustement EAN-13 à 12 ou 13 chiffres
                    clean_code = self.code.zfill(12)[:12]
                    bc = EAN13(clean_code)
                else:
                    bc = Code128(self.code)

                # Extraction de la chaîne de barres ('1' pour noir, '0' pour blanc)
                bars_pattern = bc.build()[0]

                text_height = Length.from_pt(10) if self.show_text else 0.0
                bars_rect_height = max(1.0, target_rect.height() - text_height)

                module_width = target_rect.width() / len(bars_pattern)

                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor(self.bar_color)))

                path = QPainterPath()
                for i, bit in enumerate(bars_pattern):
                    if bit == "1":
                        x = target_rect.x() + i * module_width
                        y = target_rect.y()
                        path.addRect(QRectF(x, y, module_width + 0.05, bars_rect_height))
                painter.drawPath(path)

                # Affichage du texte sous les barres
                if self.show_text:
                    painter.setPen(QColor(self.bar_color))
                    font = QFont("Monospace")
                    font.setPointSizeF(8.0)
                    painter.setFont(font)
                    text_rect = QRectF(
                        target_rect.x(),
                        target_rect.y() + bars_rect_height,
                        target_rect.width(),
                        text_height
                    )
                    painter.drawText(text_rect, Qt.AlignCenter, self.code)

            except Exception as err:
                # Gestion des erreurs de checksum ou de formatage de code
                painter.setPen(QPen(QColor("#d32f2f"), 1.0))
                painter.drawRect(target_rect)
                painter.drawText(target_rect, Qt.AlignCenter, f"Code Erreur: {err}")
        else:
            painter.setPen(QPen(QColor(self.bar_color), 1.0, Qt.DashLine))
            painter.drawRect(target_rect)
            msg = f"[ Barcode: {self.code} ]" if HAS_BARCODE else "[ install 'python-barcode' ]"
            painter.drawText(target_rect, Qt.AlignCenter, msg)

        painter.restore()


class LineItem(BaseItem):
    """Ligne séparatrice vectorielle avec gestion des styles de tirets et d'épaisseurs."""

    def __init__(
        self,
        rect: QRectF,
        color: str = "#000000",
        thickness: float = 1.0,
        style: Qt.PenStyle = Qt.SolidLine,
        rotation: float = 0.0,
        z_index: int = 0
    ):
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

        # Tracé d'une ligne reliant le coin supérieur gauche au coin supérieur droit (ou diagonale si spécifié)
        y_center = target_rect.y() + target_rect.height() / 2.0
        painter.drawLine(
            QPointF(target_rect.left(), y_center),
            QPointF(target_rect.right(), y_center)
        )
        painter.restore()


class EllipseItem(BaseItem):
    """Élément elliptique ou circulaire vectoriel."""

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

        if self.border_width > 0:
            painter.setPen(QPen(QColor(self.border_color), self.border_width))
        else:
            painter.setPen(Qt.NoPen)

        if self.fill_color:
            painter.setBrush(QBrush(QColor(self.fill_color)))
        else:
            painter.setBrush(Qt.NoBrush)

        painter.drawEllipse(target_rect)
        painter.restore()


# Enregistrement automatique de tous les nouveaux composants dans l'ItemFactory
ItemFactory.register("image", ImageItem)
ItemFactory.register("qrcode", QRCodeItem)
ItemFactory.register("barcode", BarcodeItem)
ItemFactory.register("line", LineItem)
ItemFactory.register("ellipse", EllipseItem)