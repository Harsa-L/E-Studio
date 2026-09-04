"""Widget Qt d'édition dynamique à l'écran."""

from __future__ import annotations
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor
from PySide6.QtWidgets import QWidget

from items import TextItem
from cursor import TextCursor


class TextItemView(QWidget):
    """Composant UI interactif pour l'édition dynamique sur le canvas."""

    def __init__(self, item: TextItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.cursor = TextCursor(item)
        self._layout_result = self.item.engine.layout(item)

        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_InputMethodEnabled, True)
        self.setMouseTracking(True)

        self._blink = True
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._toggle_blink)
        self._timer.start(500)

        self._selected = True
        self._edit_mode = False

        self.setGeometry(self.item.rect.toRect())

    def _toggle_blink(self):
        self._blink = not self._blink
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        local_rect = QRectF(0, 0, self.width(), self.height())
        self.item.render(painter, override_rect=local_rect)

        if self._edit_mode:
            content = self.item.content_rect_for(local_rect)
            v_offset = self.item._vertical_offset(self._layout_result, content)
            if self.cursor.has_selection():
                self._paint_selection(painter, content, v_offset)
            elif self._blink and self.hasFocus():
                self._paint_caret(painter, content, v_offset)

        if self._selected:
            painter.setPen(QPen(QColor("#2878d4"), 1, Qt.DashLine))
            painter.drawRect(self.rect().adjusted(1, 1, -2, -2))

    def _paint_caret(self, painter: QPainter, content: QRectF, v_offset: float):
        rect = self.item.engine.cursor_rect(self._layout_result, self.cursor.position.para, self.cursor.position.char)
        rect = rect.translated(content.left(), content.top() + v_offset)
        painter.fillRect(rect, QColor("#000000"))

    def _paint_selection(self, painter: QPainter, content: QRectF, v_offset: float):
        start, end = self.cursor.selection_range()
        painter.save()
        painter.translate(content.left(), content.top() + v_offset)
        brush = QBrush(QColor(100, 150, 255, 90))
        for pi in range(start.para, end.para + 1):
            pl = self._layout_result.paragraph_layouts[pi]
            a = start.char if pi == start.para else 0
            b = end.char if pi == end.para else len(pl.paragraph)
            for li in range(pl.qlayout.lineCount()):
                line = pl.qlayout.lineAt(li)
                l_start = max(0, line.textStart() - pl.text_offset)
                l_end = min(len(pl.paragraph), l_start + line.textLength() - pl.text_offset)
                sel_a = max(a, l_start)
                sel_b = min(b, l_end)
                if sel_a < sel_b:
                    x1 = line.cursorToX(sel_a + pl.text_offset)[0] if isinstance(line.cursorToX(sel_a + pl.text_offset), tuple) else line.cursorToX(sel_a + pl.text_offset)
                    x2 = line.cursorToX(sel_b + pl.text_offset)[0] if isinstance(line.cursorToX(sel_b + pl.text_offset), tuple) else line.cursorToX(sel_b + pl.text_offset)
                    y = pl.y_top + line.position().y()
                    painter.fillRect(QRectF(x1, y, x2 - x1, line.height()), brush)
        painter.restore()

    def keyPressEvent(self, event):
        text = event.text()
        key = event.key()
        modifiers = event.modifiers()

        if modifiers & Qt.ControlModifier and key == Qt.Key_Z:
            if self.cursor.undo():
                self._relayout()
            return
        if key == Qt.Key_Backspace:
            self.cursor.backspace()
        elif text and text.isprintable():
            self.cursor.insert_text(text)
        else:
            return super().keyPressEvent(event)

        self._relayout()

    def _relayout(self):
        self._layout_result = self.item.engine.layout(self.item)
        self.update()