"""Pure-Python workflow controller that keeps workspace UI separate from core document actions."""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog, QMessageBox

from core.models.template_model import LabelTemplate
from core.models.template_library import TemplateLibrary
from core.settings.app_settings import TemplateDiscoveryMode
from core.workflows.generation_session import TemplateSnapshot
from ui.windows.generation_window import GenerationWindow
from ui.windows.settings_window import SettingsWindow
from ui.windows.template_editor_window import TemplateEditorWindow


class WorkspaceController:
    """Thin workflow layer for document discovery, creation, and generation."""

    def __init__(self, settings: QSettings, parent=None) -> None:
        self.settings = settings
        self.parent = parent
        self.open_documents: list[object] = []

    def library(self) -> TemplateLibrary:
        folder = self.settings.value("template_folder", "", type=str)
        recent = self.settings.value("recent_files", [], type=list)
        managed = self.settings.value("managed_templates", [], type=list)
        mode = self.settings.value("discovery_mode", TemplateDiscoveryMode.FOLDER_AND_RECENT.value, type=str)
        if mode == TemplateDiscoveryMode.MANAGED_LIBRARY.value:
            folder = None
            recent = []
        return TemplateLibrary(folder or None, recent, managed)

    def discover_templates(self):
        return self.library().discover()

    def add_to_library(self) -> bool:
        path, _ = QFileDialog.getOpenFileName(self.parent, "Ajouter un gabarit", "", "Gabarit JSON (*.json)")
        if not path:
            return False
        managed = self.settings.value("managed_templates", [], type=list)
        self.settings.setValue("managed_templates", list(dict.fromkeys([*managed, path])))
        return True

    def create_template(self) -> None:
        editor = TemplateEditorWindow(self.parent)
        self.open_documents.append(editor)
        editor.show()
        editor.on_file_new_gabarit()

    def open_template(self, path: str) -> None:
        editor = TemplateEditorWindow(self.parent)
        self.open_documents.append(editor)
        editor.show()
        editor._open_path(path)

    def generate_template(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as source:
                template = LabelTemplate.from_json(source.read())
            window = GenerationWindow(TemplateSnapshot.from_template(template, path), self.parent)
            self.open_documents.append(window)
            window.show()
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self.parent, "Gabarit invalide", str(error))

    def open_settings(self) -> bool:
        return bool(SettingsWindow(self.parent, self.settings).exec())
