"""Calculateur de disposition grille multi-étiquettes sur papier physique."""

from dataclasses import dataclass
from template_model import Margins


@dataclass
class PageImpositionResult:
    cols: int
    rows: int
    total_per_page: int
    horizontal_offset_mm: float
    vertical_offset_mm: float


class ImpositionCalculator:
    """Calcule l'imposition maximale d'un gabarit sur une feuille physique."""

    PAGE_SIZES = {
        "A4": (210.0, 297.0),
        "A3": (297.0, 420.0),
        "LETTER": (215.9, 279.4)
    }

    @classmethod
    def calculate(
        cls,
        template_w_mm: float,
        template_h_mm: float,
        outer_margins: Margins,
        page_size_name: str = "A4",
        gap_mm: float = 0.0
    ) -> PageImpositionResult:
        page_w, page_h = cls.PAGE_SIZES.get(page_size_name.upper(), (210.0, 297.0))

        total_w = template_w_mm + outer_margins.left + outer_margins.right
        total_h = template_h_mm + outer_margins.top + outer_margins.bottom

        cols = int(page_w // (total_w + gap_mm))
        rows = int(page_h // (total_h + gap_mm))

        used_w = cols * total_w + max(0, cols - 1) * gap_mm
        used_h = rows * total_h + max(0, rows - 1) * gap_mm

        return PageImpositionResult(
            cols=cols,
            rows=rows,
            total_per_page=cols * rows,
            horizontal_offset_mm=(page_w - used_w) / 2.0,
            vertical_offset_mm=(page_h - used_h) / 2.0
        )