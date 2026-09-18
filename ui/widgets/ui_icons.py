"""Reusable UI icon-button primitives for the desktop app."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPaintEvent, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLayout, QPushButton, QWidgetItem

RESOURCE_ROOT = Path(__file__).resolve().parent / "resources" / "Icons"


class FlowLayout(QLayout):
    """A small wrap-aware layout so desktop toolbars stay responsive."""

    def __init__(self, parent=None, margin=0, spacing=0):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self._spacing = spacing
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def addWidget(self, widget):
        self.addChildWidget(widget)
        self._items.append(QWidgetItem(widget))

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            widget = item.widget()
            if widget is None:
                continue
            size = size.expandedTo(widget.sizeHint())
        margins = self.contentsMargins()
        return QSize(size.width() + margins.left() + margins.right(), size.height() + margins.top() + margins.bottom())

    def _doLayout(self, rect, testOnly=False):
        x = rect.x() + self.contentsMargins().left()
        y = rect.y() + self.contentsMargins().top()
        line_height = 0

        for item in self._items:
            widget = item.widget()
            if widget is None:
                continue
            size_hint = widget.sizeHint()
            if x > rect.x() + self.contentsMargins().left() and x + size_hint.width() > rect.right() - self.contentsMargins().right():
                x = rect.x() + self.contentsMargins().left()
                y += line_height + self._spacing
                line_height = 0
            if not testOnly:
                widget.setGeometry(QRect(QPoint(x, y), size_hint))
            line_height = max(line_height, size_hint.height())
            x += size_hint.width() + self._spacing
        return y + line_height - rect.y() + self.contentsMargins().bottom()


def _icon_button_size(size_tier: str) -> int:
    return {"xs": 24, "sm": 32, "md": 40, "lg": 48}.get(size_tier, 32)


class IconToolButton(QPushButton):
    """A frameless SVG-driven action button tuned for dense desktop toolbars."""

    def __init__(
        self,
        *,
        icon_name: str,
        icon_group: str,
        label: str,
        size_tier: str = "md",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self._icon_group = icon_group
        self._label = label
        self._size_tier = size_tier
        self._frame_size = _icon_button_size(size_tier)
        self.setFixedSize(self._frame_size, self._frame_size)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(label)
        self.setAccessibleName(label)
        self.setCheckable(False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setStyleSheet("QPushButton { border: none; background: transparent; padding: 0; margin: 0; }")

    @property
    def _svg_path(self) -> Path:
        return RESOURCE_ROOT / self._icon_group / f"{self._icon_name}.svg"

    def _paint_background(self, painter: QPainter) -> None:
        frame = self.rect()
        radius = 8 if self._frame_size <= 40 else 10

        if self.isChecked():
            painter.setPen(QColor("#38bdf8"))
            painter.setBrush(QColor("#1d4ed8"))
            painter.drawRoundedRect(frame.adjusted(1, 1, -1, -1), radius, radius)
            return

        if self.isEnabled() and (self.isDown() or self.underMouse()):
            painter.setPen(QColor("#334155"))
            painter.setBrush(QColor("#1e293b"))
            painter.drawRoundedRect(frame.adjusted(1, 1, -1, -1), radius, radius)
            return

        painter.setPen(QColor(148, 163, 184, 0))
        painter.setBrush(QColor(15, 23, 42, 0))
        painter.drawRoundedRect(frame.adjusted(1, 1, -1, -1), radius, radius)

    def _icon_color(self) -> QColor:
        if not self.isEnabled():
            return QColor("#7b8798")
        if self.isChecked():
            return QColor("#f8fafc")
        if self.isDown() or self.underMouse():
            return QColor("#f8fafc")
        return QColor("#dfe8f8")

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            self._paint_background(painter)

            svg_path = self._svg_path
            if not svg_path.exists():
                return

            renderer = QSvgRenderer(str(svg_path))
            if not renderer.isValid():
                return

            icon_size = max(14, self._frame_size - 12)
            pixmap = QPixmap(icon_size, icon_size)
            pixmap.fill(Qt.transparent)
            icon_painter = QPainter(pixmap)
            try:
                icon_painter.setRenderHint(QPainter.Antialiasing, True)
                renderer.render(icon_painter)
            finally:
                icon_painter.end()

            color = self._icon_color()
            tinted = QPixmap(pixmap.size())
            tinted.fill(Qt.transparent)
            tint_painter = QPainter(tinted)
            try:
                tint_painter.setCompositionMode(QPainter.CompositionMode_Source)
                tint_painter.drawPixmap(0, 0, pixmap)
                tint_painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
                tint_painter.fillRect(tinted.rect(), color)
            finally:
                tint_painter.end()

            target = self.rect().adjusted(
                (self.width() - icon_size) // 2,
                (self.height() - icon_size) // 2,
                -(self.width() - icon_size) // 2,
                -(self.height() - icon_size) // 2,
            )
            painter.drawPixmap(target, tinted)
        finally:
            painter.end()

    def sizeHint(self) -> QSize:
        return QSize(self._frame_size, self._frame_size)


def make_icon_button(
    *,
    icon_name: str,
    icon_group: str,
    label: str,
    size_tier: str = "md",
    parent=None,
) -> IconToolButton:
    return IconToolButton(icon_name=icon_name, icon_group=icon_group, label=label, size_tier=size_tier, parent=parent)


def svg_icon_path(icon_name: str, icon_group: str) -> Path:
    return RESOURCE_ROOT / icon_group / f"{icon_name}.svg"


def make_svg_action(
    *,
    icon_name: str,
    icon_group: str,
    label: str,
    parent=None,
    enabled: bool = True,
):
    from PySide6.QtGui import QAction

    action = QAction(label, parent)
    path = svg_icon_path(icon_name, icon_group)
    if path.exists():
        action.setIcon(QIcon(str(path)))
    action.setToolTip(label)
    action.setStatusTip(label)
    action.setEnabled(enabled)
    action.setShortcutVisibleInContextMenu(True)
    return action
