"""Home route for selecting, creating, editing, and generating gabarits."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QHBoxLayout, QVBoxLayout, QWidget

from generation_session import TemplateSnapshot
from generation_window import GenerationWindow
from settings_window import SettingsWindow
from template_library import TemplateLibrary
from template_model import LabelTemplate
from template_editor_window import TemplateEditorWindow
from app_settings import TemplateDiscoveryMode


class HomeWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("E-Studio — Gabarits")
        self.resize(900, 620)
        self.settings = QSettings("E-Studio", "E-Studio")
        self.editor_windows = []
        self.generation_windows = []
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self.open_selected_editor)
        self.refresh_button = QPushButton("Actualiser")
        self.refresh_button.clicked.connect(self.refresh)
        self.new_button = QPushButton("Créer un gabarit")
        self.new_button.clicked.connect(self.create_template)
        self.edit_button = QPushButton("Éditer")
        self.edit_button.clicked.connect(self.open_selected_editor)
        self.generate_button = QPushButton("Générer des étiquettes")
        self.generate_button.clicked.connect(self.generate_selected)
        self.settings_button = QPushButton("Paramètres")
        self.settings_button.clicked.connect(self.open_settings)
        self.library_button = QPushButton("Ajouter à la bibliothèque")
        self.library_button.clicked.connect(self.add_to_library)
        buttons = QHBoxLayout()
        for button in (self.new_button, self.edit_button, self.generate_button, self.refresh_button, self.settings_button, self.library_button):
            buttons.addWidget(button)
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.addLayout(buttons)
        layout.addWidget(self.list)
        self.setCentralWidget(root)
        self.refresh()

    def _library(self) -> TemplateLibrary:
        folder = self.settings.value("template_folder", "", type=str)
        recent = self.settings.value("recent_files", [], type=list)
        managed = self.settings.value("managed_templates", [], type=list)
        mode = self.settings.value("discovery_mode", TemplateDiscoveryMode.FOLDER_AND_RECENT.value, type=str)
        if mode == TemplateDiscoveryMode.MANAGED_LIBRARY.value:
            folder = None
            recent = []
        return TemplateLibrary(folder or None, recent, managed)

    def add_to_library(self):
        path, _ = QFileDialog.getOpenFileName(self, "Ajouter un gabarit", "", "Gabarit JSON (*.json)")
        if not path:
            return
        managed = self.settings.value("managed_templates", [], type=list)
        self.settings.setValue("managed_templates", list(dict.fromkeys([*managed, path])))
        self.refresh()

    def refresh(self):
        self.list.clear()
        for summary in self._library().discover():
            label = summary.name or Path(summary.path).name
            if not summary.valid:
                label += f"  [invalide: {summary.error}]"
            item = QListWidgetItem(label)
            item.setData(256, summary.path)
            item.setData(257, summary.valid)
            self.list.addItem(item)
        if not self.list.count():
            self.list.addItem("Aucun gabarit. Créez votre premier gabarit.")

    def _selected_path(self) -> str | None:
        item = self.list.currentItem()
        if not item or not item.data(257):
            return None
        return str(item.data(256))

    def create_template(self):
        editor = TemplateEditorWindow(self)
        self.editor_windows.append(editor)
        editor.show()
        editor.on_file_new_gabarit()

    def open_selected_editor(self):
        path = self._selected_path()
        if not path:
            return
        editor = TemplateEditorWindow(self)
        self.editor_windows.append(editor)
        editor.show()
        editor._open_path(path)

    def generate_selected(self):
        path = self._selected_path()
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as source:
                template = LabelTemplate.from_json(source.read())
            window = GenerationWindow(TemplateSnapshot.from_template(template, path), self)
            self.generation_windows.append(window)
            window.show()
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Gabarit invalide", str(error))

    def open_settings(self):
        if SettingsWindow(self, self.settings).exec():
            self.refresh()
