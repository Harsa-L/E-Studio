"""Value Objects pour la gestion immuable des unités physiques et sub-pixel."""

from __future__ import annotations
from enum import Enum


class Unit(str, Enum):
    PIXEL = "px"
    MILLIMETER = "mm"
    POINT = "pt"


class Length(float):
    """Encapsule une mesure sous forme de float représentant des pixels (unité de base).
    
    Inspiré de pptx.util, permet d'écrire du code expressif comme :
    `rect.setWidth(Length.from_mm(80))` sans repasser le DPI partout.
    """

    @classmethod
    def from_px(cls, px: float) -> Length:
        return cls(px)

    @classmethod
    def from_mm(cls, mm: float, dpi: float = 300.0) -> Length:
        if dpi <= 0:
            raise ValueError("Le DPI doit être supérieur à zéro.")
        return cls(mm * dpi / 25.4)

    @classmethod
    def from_pt(cls, pt: float, dpi: float = 300.0) -> Length:
        if dpi <= 0:
            raise ValueError("Le DPI doit être supérieur à zéro.")
        return cls(pt * dpi / 72.0)

    def to_px(self) -> float:
        return float(self)

    def to_mm(self, dpi: float = 300.0) -> float:
        if dpi <= 0:
            raise ValueError("Le DPI doit être supérieur à zéro.")
        return float(self) * 25.4 / dpi

    def to_pt(self, dpi: float = 300.0) -> float:
        if dpi <= 0:
            raise ValueError("Le DPI doit être supérieur à zéro.")
        return float(self) * 72.0 / dpi