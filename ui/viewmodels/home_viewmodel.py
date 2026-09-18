"""MVVM/state layer for the home workspace UI."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from app.application_service import AppService, WorkspaceState


class HomeViewModel(QObject):
    """Exposes UI state via Qt signals while keeping business logic in the app service."""

    templates_changed = Signal(list)
    status_changed = Signal(str)
    open_editor_requested = Signal(str)
    open_generation_requested = Signal(str)
    refresh_requested = Signal()

    def __init__(self, app_service: AppService):
        super().__init__()
        self.app_service = app_service

    def load_templates(self) -> None:
        summaries = self.app_service.discover_templates()
        state = WorkspaceState(templates=summaries)
        self.templates_changed.emit(state.templates)
        self.status_changed.emit("Workspace ready")

    def request_open_editor(self, path: str | None = None) -> None:
        if path:
            self.open_editor_requested.emit(path)

    def request_open_generation(self, path: str) -> None:
        self.open_generation_requested.emit(path)

    def refresh(self) -> None:
        self.refresh_requested.emit()
        self.load_templates()
