"""Moteur de calcul de layout typographique et d'ajustement automatique."""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional, TYPE_CHECKING
from PySide6.QtCore import QRectF, QPointF, Qt
from PySide6.QtGui import QFont, QTextLayout, QTextOption, QTextCharFormat, QTextLine, QColor

from .models import CharFormat, Paragraph, Overflow, TextAlignment

if TYPE_CHECKING:
    from .items import TextItem


# Mapping entre le domaine métier (TextAlignment) et l'IHM (Qt)
ALIGNMENT_MAP = {
    TextAlignment.LEFT: Qt.AlignLeft,
    TextAlignment.CENTER: Qt.AlignHCenter,
    TextAlignment.RIGHT: Qt.AlignRight,
    TextAlignment.JUSTIFY: Qt.AlignJustified,
}


def _qfont_default(scale: float) -> QFont:
    f = QFont("Arial")
    f.setPointSizeF(max(1.0, 18.0 * scale))
    return f


def _qfont(fmt: CharFormat, scale: float) -> QFont:
    f = QFont(fmt.font_family)
    f.setPointSizeF(max(1.0, fmt.font_size * scale))
    f.setBold(fmt.bold)
    f.setItalic(fmt.italic)
    f.setUnderline(fmt.underline)
    f.setStrikeOut(fmt.strikethrough)
    if fmt.tracking:
        f.setLetterSpacing(QFont.AbsoluteSpacing, fmt.tracking * scale)
    if fmt.small_caps:
        f.setCapitalization(QFont.SmallCaps)
    return f


@dataclass
class ParagraphLayout:
    paragraph: Paragraph
    qlayout: QTextLayout
    y_top: float
    height: float
    text_offset: int = 0


@dataclass
class LayoutResult:
    paragraph_layouts: List[ParagraphLayout]
    total_height: float
    font_scale: float
    fits: bool


class LayoutEngine:
    MIN_SCALE = 0.15
    BINARY_SEARCH_ITERATIONS = 7

    def layout(self, obj: TextItem, content_rect: Optional[QRectF] = None) -> LayoutResult:
        content = content_rect or obj.content_rect_for(obj.rect)
        width = content.width() if obj.wrap else 1_000_000.0

        if obj.overflow == Overflow.AUTOFIT_SHRINK:
            low, high = self.MIN_SCALE, 1.0
            best_scale = low
            best_result = self._layout_at_scale(obj, width, content.height(), low)

            for _ in range(self.BINARY_SEARCH_ITERATIONS):
                mid = (low + high) / 2.0
                result = self._layout_at_scale(obj, width, content.height(), mid)
                if result.fits:
                    best_scale = mid
                    best_result = result
                    low = mid
                else:
                    high = mid

            obj.font_scale = best_scale
            return best_result
        else:
            result = self._layout_at_scale(obj, width, content.height(), 1.0)
            if obj.overflow == Overflow.AUTOFIT_GROW and not result.fits:
                l, r, t, b = obj.margins
                obj.rect.setHeight(max(obj.rect.height(), result.total_height + t + b))
                content = obj.content_rect_for(obj.rect)
                result = self._layout_at_scale(obj, width, content.height(), 1.0)
            obj.font_scale = 1.0
            return result

    def _layout_at_scale(self, obj: TextItem, width: float, max_height: float, scale: float) -> LayoutResult:
        paragraph_layouts: List[ParagraphLayout] = []
        y = 0.0

        for para in obj.paragraphs:
            y += para.pformat.space_before * scale
            prefix = (para.pformat.bullet + " ") if para.pformat.bullet else ""
            para_text = para.text
            display_text = prefix + (para_text if para_text else " ")
            text_offset = len(prefix)

            qlayout = QTextLayout(display_text)
            option = QTextOption(ALIGNMENT_MAP[para.pformat.alignment])
            option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere if width < 1_000_000 else QTextOption.NoWrap)
            qlayout.setTextOption(option)

            formats = []
            max_size = 0.0
            dominant_fmt = para.runs[0].format if para.runs else None
            current_pos = text_offset

            # Parcours ultra-efficace basé sur les Runs (Style python-pptx)
            for run in para.runs:
                run_len = len(run.text)
                if run_len == 0:
                    continue

                cf = QTextCharFormat()
                cf.setFont(_qfont(run.format, scale))
                cf.setForeground(QColor(run.format.color))
                if run.format.baseline_shift > 0:
                    cf.setVerticalAlignment(QTextCharFormat.AlignSuperScript)
                elif run.format.baseline_shift < 0:
                    cf.setVerticalAlignment(QTextCharFormat.AlignSubScript)

                formats.append(QTextLayout.FormatRange(start=current_pos, length=run_len, format=cf))

                if run.format.font_size > max_size:
                    max_size = run.format.font_size
                    dominant_fmt = run.format

                current_pos += run_len

            qlayout.setFormats(formats)
            qlayout.setFont(_qfont(dominant_fmt, scale) if dominant_fmt else _qfont_default(scale))

            indent_l = para.pformat.indent_left
            indent_first = para.pformat.indent_first_line
            line_spacing = para.pformat.line_spacing * (1.0 - obj.line_spacing_reduction)

            qlayout.beginLayout()
            para_top = y
            first_line = True
            while True:
                line = qlayout.createLine()
                if not line.isValid():
                    break
                avail = max(1.0, width - indent_l - (indent_first if first_line else 0.0) - para.pformat.indent_right)
                line.setLineWidth(avail)
                line_x = indent_l + (indent_first if first_line else 0.0)
                line.setPosition(QPointF(line_x, y - para_top))
                y += line.height() * line_spacing
                first_line = False
            qlayout.endLayout()

            y += para.pformat.space_after * scale
            paragraph_layouts.append(ParagraphLayout(
                paragraph=para, qlayout=qlayout, y_top=para_top, height=y - para_top, text_offset=text_offset
            ))

        total_height = y
        fits = total_height <= max_height + 0.5
        return LayoutResult(paragraph_layouts, total_height, scale, fits)

    def cursor_rect(self, result: LayoutResult, para: int, char: int) -> QRectF:
        pl = result.paragraph_layouts[para]
        char = max(0, min(len(pl.paragraph), char))
        display_char = char + pl.text_offset
        line = pl.qlayout.lineForTextPosition(display_char)
        if not line.isValid():
            line = pl.qlayout.lineAt(max(0, pl.qlayout.lineCount() - 1))
        x_val = line.cursorToX(display_char)
        x = x_val[0] if isinstance(x_val, tuple) else x_val
        y = pl.y_top + line.position().y()
        return QRectF(x, y, 1.5, line.height())