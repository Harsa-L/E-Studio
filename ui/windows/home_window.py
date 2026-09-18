"""Home route for selecting, creating, editing, and generating gabarits."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QHBoxLayout,
    QMdiArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.application_service import AppService
from ui.viewmodels.home_viewmodel import HomeViewModel
from ui.windows.generation_window import GenerationWindow
from ui.windows.template_editor_window import TemplateEditorWindow
from core.models.template_model import LabelTemplate
from ui.widgets.ui_icons import FlowLayout, make_icon_button
from ui.controllers.workspace_controller import WorkspaceController


class HomeWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("E-Studio — Gabarits")
        self.resize(1100, 700)
        self.setObjectName("homeWindow")
        self.settings = QSettings("E-Studio", "E-Studio")
        self.controller = WorkspaceController(self.settings, self)
        self.app_service = AppService(self.settings)
        self.view_model = HomeViewModel(self.app_service)
        self.view_model.templates_changed.connect(self._render_templates)
        self.view_model.status_changed.connect(self.statusBar().showMessage)
        self.view_model.open_editor_requested.connect(self._open_editor_in_workspace)
        self.view_model.open_generation_requested.connect(self._open_generation_in_workspace)
        self.statusBar().showMessage("Workspace ready")

        self.list = QListWidget()
        self.list.setObjectName("templateList")
        self.list.setAlternatingRowColors(True)
        self.list.setUniformItemSizes(True)
        self.list.setSpacing(2)
        self.list.itemDoubleClicked.connect(self.open_selected_editor)

        self.recent_list = QListWidget()
        self.recent_list.setObjectName("recentList")
        self.recent_list.setAlternatingRowColors(True)
        self.recent_list.setUniformItemSizes(True)
        self.recent_list.setSpacing(2)
        self.recent_list.itemDoubleClicked.connect(self.open_selected_editor)

        self.refresh_button = make_icon_button(icon_name="refresh_1", icon_group="system", label="Actualiser", size_tier="md")
        self.refresh_button.clicked.connect(self.refresh)
        self.new_button = make_icon_button(icon_name="add", icon_group="system", label="Créer un gabarit", size_tier="md")
        self.new_button.clicked.connect(self.create_template)
        self.edit_button = make_icon_button(icon_name="edit_2", icon_group="editing", label="Éditer", size_tier="md")
        self.edit_button.clicked.connect(self.open_selected_editor)
        self.generate_button = make_icon_button(icon_name="file_export", icon_group="files", label="Générer des étiquettes", size_tier="md")
        self.generate_button.clicked.connect(self.generate_selected)
        self.settings_button = make_icon_button(icon_name="settings_1", icon_group="system", label="Paramètres", size_tier="md")
        self.settings_button.clicked.connect(self.open_settings)
        self.library_button = make_icon_button(icon_name="folder_upload", icon_group="files", label="Ajouter à la bibliothèque", size_tier="md")
        self.library_button.clicked.connect(self.add_to_library)

        self.title_bar = QWidget(self)
        self.title_bar.setObjectName("homeHeader")
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(18, 12, 18, 10)
        title_layout.setSpacing(12)

        self.brand_label = QLabel("E-Studio")
        title_layout.addWidget(self.brand_label)
        title_layout.addStretch()

        for button in (self.new_button, self.edit_button, self.generate_button, self.refresh_button, self.settings_button, self.library_button):
            title_layout.addWidget(button)

        self.toolbar = QWidget(self)
        self.toolbar.setObjectName("homeToolbar")
        command_layout = QHBoxLayout(self.toolbar)
        command_layout.setContentsMargins(18, 8, 18, 8)
        command_layout.setSpacing(8)
        command_layout.addWidget(QLabel("Workspace"))
        command_layout.addStretch()

        self.sidebar = QWidget(self)
        self.sidebar.setObjectName("homeSidebar")
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(14, 14, 14, 14)
        side_layout.setSpacing(10)

        side_layout.addWidget(QLabel("Menu"))
        for label, button in (
            ("Nouveau", self.new_button),
            ("Éditer", self.edit_button),
            ("Générer", self.generate_button),
            ("Bibliothèque", self.library_button),
            ("Réglages", self.settings_button),
        ):
            group_label = QLabel(label)
            group_label.setWordWrap(True)
            side_layout.addWidget(group_label)
            side_layout.addWidget(button)
        side_layout.addStretch()

        self.content_panel = QWidget(self)
        self.content_panel.setObjectName("templateListPanel")
        content_layout = QVBoxLayout(self.content_panel)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(10)

        self.list_tabs = QTabWidget(self.content_panel)
        self.list_tabs.setTabPosition(QTabWidget.North)

        templates_tab = QWidget(self.list_tabs)
        templates_layout = QVBoxLayout(templates_tab)
        templates_layout.setContentsMargins(0, 8, 0, 0)
        templates_layout.setSpacing(8)
        templates_layout.addWidget(QLabel("Modèles disponibles"))
        templates_layout.addWidget(self.list)
        self.list_tabs.addTab(templates_tab, "Templates")

        recent_tab = QWidget(self.list_tabs)
        recent_layout = QVBoxLayout(recent_tab)
        recent_layout.setContentsMargins(0, 8, 0, 0)
        recent_layout.setSpacing(8)
        recent_layout.addWidget(QLabel("Récents"))
        recent_layout.addWidget(self.recent_list)
        self.list_tabs.addTab(recent_tab, "Récents")

        content_layout.addWidget(self.list_tabs)

        self.workspace = QMdiArea(self)
        self.workspace.setViewMode(QMdiArea.TabbedView)
        self.workspace.setTabsClosable(True)
        self.workspace.setTabsMovable(True)
        self.workspace.setDocumentMode(True)
        self.workspace.setActivationOrder(QMdiArea.ActivationHistoryOrder)
        self.workspace.subWindowActivated.connect(self._update_workspace_status)

        root = QWidget(self)
        root.setObjectName("homeRoot")
        shell_layout = QHBoxLayout(root)
        shell_layout.setContentsMargins(18, 16, 18, 18)
        shell_layout.setSpacing(16)
        shell_layout.addWidget(self.sidebar, 0)
        shell_layout.addWidget(self.content_panel, 1)
        shell_layout.addWidget(self.workspace, 3)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.title_bar)
        layout.addWidget(self.toolbar)
        layout.addWidget(root)

        container = QWidget(self)
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.refresh()

    def add_to_library(self):
        if self.controller.add_to_library():
            self.refresh()

    def _render_templates(self, summaries):
        self.list.clear()
        self.recent_list.clear()
        for summary in summaries:
            label = summary.name
            if not summary.valid:
                label += f"  [invalide]: {summary.error}" if summary.error else "  [invalide]"
            item = QListWidgetItem(label)
            item.setData(256, summary.path)
            item.setData(257, summary.valid)
            self.list.addItem(item)
            self.recent_list.addItem(item.clone())
        if not self.list.count():
            empty = "Aucun gabarit. Créez votre premier gabarit."
            self.list.addItem(empty)
            self.recent_list.addItem(empty)

    def refresh(self):
        self.view_model.load_templates()

    def _selected_path(self) -> str | None:
        item = self.list.currentItem()
        if not item or not item.data(257):
            return None
        return str(item.data(256))

    def _update_workspace_status(self):
        active = self.workspace.activeSubWindow()
        if active is None:
            self.statusBar().showMessage("Workspace ready")
            return
        widget = active.widget()
        title = getattr(widget, "windowTitle", lambda: "Document")()
        if hasattr(widget, "document_title"):
            title = widget.document_title.text()
        self.statusBar().showMessage(f"Active document: {title}")

    def _open_editor_in_workspace(self, path: str | None = None):
        editor = TemplateEditorWindow(self)
        editor.setAttribute(Qt.WA_DeleteOnClose, True)
        self.workspace.addSubWindow(editor)
        editor.show()
        if path:
            editor._open_path(path)
        else:
            editor.on_file_new_gabarit()
        self._update_workspace_status()

    def _open_generation_in_workspace(self, path: str):
        with open(path, "r", encoding="utf-8") as source:
            template = LabelTemplate.from_json(source.read())
        window = GenerationWindow(TemplateSnapshot.from_template(template, path), self)
        window.setAttribute(Qt.WA_DeleteOnClose, True)
        self.workspace.addSubWindow(window)
        window.show()
        self._update_workspace_status()

    def create_template(self):
        self._open_editor_in_workspace()

    def open_selected_editor(self):
        path = self._selected_path()
        if not path:
            return
        self._open_editor_in_workspace(path)

    def generate_selected(self):
        path = self._selected_path()
        if not path:
            return
        self._open_generation_in_workspace(path)

    def open_settings(self):
        if self.controller.open_settings():
            self.refresh()
