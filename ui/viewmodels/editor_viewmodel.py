"""Pure editor state backed by Qt signals for the document window."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class EditorViewModel(QObject):
    """UI state and actions for the label editor without owning core logic."""

    title_changed = Signal(str)
    status_changed = Signal(str)
    dirty_changed = Signal(bool)
    open_requested = Signal(str)
    save_requested = Signal(str)
    create_requested = Signal()

    def __init__(self):
        super().__init__()
        self.current_path: str | None = None
        self.is_dirty = False

    def set_document(self, path: str | None, dirty: bool = False) -> None:
        self.current_path = path
        self.is_dirty = dirty
        self.title_changed.emit(self._title_text())
        self.status_changed.emit("Document prêt" if not dirty else "Modifications non enregistrées")
        self.dirty_changed.emit(dirty)

    def _title_text(self) -> str:
        name = self.current_path or "Nouveau gabarit"
        marker = " • modifié" if self.is_dirty else " • enregistré"
        return f"{name}{marker}"

    def request_open(self, path: str) -> None:
        self.open_requested.emit(path)

    def request_save(self, path: str) -> None:
        self.save_requested.emit(path)

    def request_create(self) -> None:
        self.create_requested.emit()
