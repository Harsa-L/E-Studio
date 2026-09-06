#Application principale orchestrant la création, l'édition et la sauvegarde.

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QDockWidget,
    QToolBar, QFileDialog, QMessageBox, QDialog, QFormLayout,
    QDialogButtonBox, QTableWidget, QTableWidgetItem, QPushButton,
    QHBoxLayout, QComboBox, QDoubleSpinBox, QVBoxLayout, QInputDialog,
    QProgressDialog
)
from PySide6.QtCore import Qt, QSettings, QTimer, QEventLoop, QThread, Signal
from PySide6.QtGui import QAction, QKeySequence, QCloseEvent, QUndoCommand, QUndoStack

from gabarit_wizard import NewGabaritDialog
from template_canvas import TemplateCanvas
from template_model import LabelTemplate
from property_inspector import PropertyInspectorWidget
from label_items import BaseLabelItem, DomainFieldLabelItem, RichLabelItem, TierPriceLabelItem
from binding_profiles import BindingProfile, ColumnMapping, suggest_mappings
from data_normalization import normalize_row
from data_sources import WorkbookReadError, read_xlsx
from batch_export import export_rows_as_png, export_rows_on_pages, normalize_workbook
from excel_worker import ExcelNormalizeWorker


class CanvasView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setDragMode(QGraphicsView.ScrollHandDrag)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
            event.accept()
            return
        super().wheelEvent(event)

    def fit_scene(self):
        if self.scene():
            self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)


class SnapshotCommand(QUndoCommand):
    def __init__(self, canvas, before, after, text):
        super().__init__(text)
        self.canvas = canvas
        self.before = before
        self.after = after

    def undo(self):
        self.canvas.restore_item_snapshot(self.before)

    def redo(self):
        self.canvas.restore_item_snapshot(self.after)


class PreviewDataDialog(QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Données d'aperçu")
        self.resize(520, 360)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["Clé", "Valeur"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        add_button = QPushButton("Ajouter")
        add_button.clicked.connect(self._add_row)
        remove_button = QPushButton("Supprimer")
        remove_button.clicked.connect(self._remove_row)
        load_button = QPushButton("Importer JSON")
        load_button.clicked.connect(self._load_json)
        buttons.addWidget(add_button)
        buttons.addWidget(remove_button)
        buttons.addWidget(load_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)
        layout.addWidget(dialog_buttons)
        for key, value in data.items():
            self._add_row(str(key), str(value))

    def _add_row(self, key="", value=""):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(key))
        self.table.setItem(row, 1, QTableWidgetItem(value))

    def _remove_row(self):
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def _load_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importer les données", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, dict):
                raise ValueError("Le fichier doit contenir un objet JSON.")
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Erreur", f"Impossible de charger les données : {error}")
            return
        self.table.setRowCount(0)
        for key, value in data.items():
            self._add_row(str(key), str(value))

    def values(self):
        result = {}
        for row in range(self.table.rowCount()):
            key_item = self.table.item(row, 0)
            value_item = self.table.item(row, 1)
            key = key_item.text().strip() if key_item else ""
            if key:
                result[key] = value_item.text() if value_item else ""
        return result


class ExportOptionsDialog(QDialog):
    def __init__(self, page=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Options d'export")
        form = QFormLayout(self)
        self.dpi = QDoubleSpinBox()
        self.dpi.setRange(30, 1200)
        self.dpi.setValue(300)
        self.dpi.setSuffix(" DPI")
        form.addRow("Résolution", self.dpi)
        self.page_size = QComboBox()
        self.page_size.addItems(["A4", "A3", "LETTER"])
        self.page_size.setEnabled(page)
        form.addRow("Format feuille", self.page_size)
        self.gap = QDoubleSpinBox()
        self.gap.setRange(0, 100)
        self.gap.setDecimals(2)
        self.gap.setSuffix(" mm")
        self.gap.setEnabled(page)
        form.addRow("Espacement", self.gap)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class MappingDialog(QDialog):
    """Edit source-column to binding-key mappings before preview/export."""

    def __init__(self, headers, suggestions=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mapping des colonnes Excel")
        self.resize(720, 420)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(len(headers), 4, self)
        self.table.setHorizontalHeaderLabels(["Colonne Excel", "Clé de binding", "Type", "Requis"])
        self.table.horizontalHeader().setStretchLastSection(True)
        types = ["text", "number", "currency", "boolean", "date", "image", "barcode", "qrcode"]
        suggestions = suggestions or {}
        for row, header in enumerate(headers):
            self.table.setItem(row, 0, QTableWidgetItem(header))
            self.table.item(row, 0).setFlags(Qt.ItemIsEnabled)
            target = suggestions.get(header, header)
            self.table.setItem(row, 1, QTableWidgetItem(target))
            combo = QComboBox(self.table)
            combo.addItems(types)
            combo.setCurrentText(suggestions.get(f"{header}:type", "text"))
            self.table.setCellWidget(row, 2, combo)
            required = QTableWidgetItem()
            required.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            required.setCheckState(Qt.Unchecked)
            self.table.setItem(row, 3, required)
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def profile(self):
        mappings = []
        for row in range(self.table.rowCount()):
            source = self.table.item(row, 0).text()
            target = self.table.item(row, 1).text().strip()
            if not target:
                continue
            combo = self.table.cellWidget(row, 2)
            required = self.table.item(row, 3).checkState() == Qt.Checked
            mappings.append(ColumnMapping(source, target, combo.currentText(), required))
        return BindingProfile(mappings=mappings)


class EditorMainWindow(QMainWindow):

    document_saved = Signal(str, object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Concepteur de Gabarits d'Étiquettes & Paliers")
        self.resize(1200, 800)

        self.canvas: Optional[TemplateCanvas] = None
        self.preview_data: Dict[str, Any] = {}
        self.excel_table = None
        self.excel_profile = None
        self.current_path: Optional[str] = None
        self.is_dirty = False
        self.view = CanvasView(self)
        self.undo_stack = QUndoStack(self)
        self.settings = QSettings("E-Studio", "E-Studio")
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(60_000)
        self.autosave_timer.timeout.connect(self._write_autosave)
        self.autosave_timer.start()
        self.setCentralWidget(self.view)

        # Dock latéral
        self.inspector = PropertyInspectorWidget(self)
        dock = QDockWidget("Inspecteur de Propriétés", self)
        dock.setWidget(self.inspector)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

        self._build_menus_and_toolbars()
        self._update_window_title()
        self._restore_autosave()

    def _build_menus_and_toolbars(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Fichier")

        act_new = QAction("Nouveau Gabarit...", self)
        act_new.setShortcut(QKeySequence.New)
        act_new.triggered.connect(self.on_file_new_gabarit)
        file_menu.addAction(act_new)

        act_save = QAction("Sauvegarder JSON", self)
        act_save.setShortcut(QKeySequence.Save)
        act_save.triggered.connect(self.on_file_save)
        file_menu.addAction(act_save)

        act_open = QAction("Ouvrir JSON", self)
        act_open.setShortcut(QKeySequence.Open)
        act_open.triggered.connect(self.on_file_open)
        file_menu.addAction(act_open)
        self.recent_menu = file_menu.addMenu("Fichiers récents")
        self._refresh_recent_menu()

        self.act_load_preview_data = QAction("Charger données d'aperçu…", self)
        self.act_load_preview_data.setEnabled(False)
        self.act_load_preview_data.triggered.connect(self.on_load_preview_data)
        file_menu.addAction(self.act_load_preview_data)

        self.act_import_excel = QAction("Importer Excel…", self)
        self.act_import_excel.setEnabled(False)
        self.act_import_excel.triggered.connect(self.on_import_excel)
        file_menu.addAction(self.act_import_excel)

        self.act_export_excel = QAction("Exporter les lignes Excel…", self)
        self.act_export_excel.setEnabled(False)
        self.act_export_excel.triggered.connect(self.on_export_excel)
        file_menu.addAction(self.act_export_excel)

        self.act_export_excel_pages = QAction("Exporter Excel sur feuilles…", self)
        self.act_export_excel_pages.setEnabled(False)
        self.act_export_excel_pages.triggered.connect(self.on_export_excel_pages)
        file_menu.addAction(self.act_export_excel_pages)

        self.act_export_png = QAction("Exporter PNG…", self)
        self.act_export_png.setEnabled(False)
        self.act_export_png.triggered.connect(self.on_export_png)
        file_menu.addAction(self.act_export_png)

        self.act_export_page_png = QAction("Exporter feuille A4…", self)
        self.act_export_page_png.setEnabled(False)
        self.act_export_page_png.triggered.connect(self.on_export_page_png)
        file_menu.addAction(self.act_export_page_png)

        edit_menu = menubar.addMenu("Édition")
        self.act_undo = self.undo_stack.createUndoAction(self, "Annuler")
        self.act_undo.setShortcut(QKeySequence.Undo)
        edit_menu.addAction(self.act_undo)
        self.act_redo = self.undo_stack.createRedoAction(self, "Rétablir")
        self.act_redo.setShortcut(QKeySequence.Redo)
        edit_menu.addAction(self.act_redo)
        self.act_delete = QAction("Supprimer la sélection", self)
        self.act_delete.setShortcut(QKeySequence.Delete)
        self.act_delete.setEnabled(False)
        self.act_delete.triggered.connect(self.on_delete_selected)
        edit_menu.addAction(self.act_delete)

        self.act_duplicate = QAction("Dupliquer la sélection", self)
        self.act_duplicate.setShortcut(QKeySequence("Ctrl+D"))
        self.act_duplicate.setEnabled(False)
        self.act_duplicate.triggered.connect(self.on_duplicate_selected)
        edit_menu.addAction(self.act_duplicate)

        self.act_copy = QAction("Copier la sélection", self)
        self.act_copy.setShortcut(QKeySequence.Copy)
        self.act_copy.setEnabled(False)
        self.act_copy.triggered.connect(self.on_copy_selected)
        edit_menu.addAction(self.act_copy)

        self.act_paste = QAction("Coller", self)
        self.act_paste.setShortcut(QKeySequence.Paste)
        self.act_paste.setEnabled(False)
        self.act_paste.triggered.connect(self.on_paste_selected)
        edit_menu.addAction(self.act_paste)

        self.act_preview = QAction("Aperçu des données", self)
        self.act_preview.setCheckable(True)
        self.act_preview.setEnabled(False)
        self.act_preview.toggled.connect(self.on_toggle_preview)
        edit_menu.addAction(self.act_preview)

        view_menu = menubar.addMenu("Affichage")
        fit_action = QAction("Adapter à la fenêtre", self)
        fit_action.setShortcut(QKeySequence("F"))
        fit_action.triggered.connect(self.view.fit_scene)
        view_menu.addAction(fit_action)
        reset_zoom = QAction("Réinitialiser le zoom", self)
        reset_zoom.setShortcut(QKeySequence("Ctrl+0"))
        reset_zoom.triggered.connect(self.view.resetTransform)
        view_menu.addAction(reset_zoom)

        insert_menu = menubar.addMenu("Insérer")

        # Barre d'outils
        toolbar = QToolBar("Actions")
        self.addToolBar(toolbar)

        self.act_add_tier = QAction("Ajouter Bloc Palier", self)
        self.act_add_tier.setEnabled(False)
        self.act_add_tier.triggered.connect(self.on_add_tier_item)
        toolbar.addAction(self.act_add_tier)

        self.rich_actions: list[QAction] = []
        rich_actions = (
            ("Texte", "text"),
            ("Rectangle", "shape"),
            ("Ellipse", "ellipse"),
            ("Image…", "image"),
            ("QR code", "qrcode"),
            ("Code-barres", "barcode"),
            ("Ligne", "line"),
        )
        for title, rich_type in rich_actions:
            action = QAction(title, self)
            action.setEnabled(False)
            action.triggered.connect(lambda checked=False, kind=rich_type: self.on_add_rich_item(kind))
            insert_menu.addAction(action)
            self.rich_actions.append(action)
            if rich_type in {"text", "image", "qrcode", "barcode"}:
                toolbar.addAction(action)

        fields_menu = insert_menu.addMenu("Champ métier")
        for field_name in RichLabelItem.DOMAIN_FIELDS:
            action = QAction(field_name, self)
            action.setEnabled(False)
            action.triggered.connect(lambda checked=False, key=field_name: self.on_add_domain_field(key))
            fields_menu.addAction(action)
            self.rich_actions.append(action)

        self.act_validate = QAction("Contrôler Dépassements", self)
        self.act_validate.setEnabled(False)
        self.act_validate.triggered.connect(self.on_validate_bounds)
        toolbar.addAction(self.act_validate)

        alignment_menu = insert_menu.addMenu("Aligner")
        for title, mode in (("À gauche", "left"), ("Centrer horizontalement", "center_horizontal"),
                            ("À droite", "right"), ("En haut", "top"),
                            ("Centrer verticalement", "center_vertical"), ("En bas", "bottom")):
            action = QAction(title, self)
            action.setEnabled(False)
            action.triggered.connect(lambda checked=False, value=mode: self.on_align(value))
            alignment_menu.addAction(action)
            self.rich_actions.append(action)
        for title, direction in (("Distribuer horizontalement", "horizontal"), ("Distribuer verticalement", "vertical")):
            action = QAction(title, self)
            action.setEnabled(False)
            action.triggered.connect(lambda checked=False, value=direction: self.on_distribute(value))
            alignment_menu.addAction(action)
            self.rich_actions.append(action)

    def _set_document_actions_enabled(self, enabled: bool):
        self.act_add_tier.setEnabled(enabled)
        self.act_validate.setEnabled(enabled)
        self.act_export_png.setEnabled(enabled)
        self.act_export_page_png.setEnabled(enabled)
        self.act_load_preview_data.setEnabled(enabled)
        self.act_import_excel.setEnabled(enabled)
        self.act_export_excel.setEnabled(enabled and self.excel_table is not None and self.excel_profile is not None)
        self.act_export_excel_pages.setEnabled(enabled and self.excel_table is not None and self.excel_profile is not None)
        self.act_delete.setEnabled(enabled)
        self.act_duplicate.setEnabled(enabled)
        self.act_paste.setEnabled(enabled)
        self.act_preview.setEnabled(enabled and bool(self.preview_data))
        for action in self.rich_actions:
            action.setEnabled(enabled)

    def _update_window_title(self):
        name = self.current_path or "Nouveau gabarit"
        marker = " *" if self.is_dirty else ""
        self.setWindowTitle(f"Concepteur de Gabarits d'Étiquettes & Paliers - {name}{marker}")

    def _mark_dirty(self):
        self.is_dirty = True
        self._update_window_title()

    def _set_canvas(self, canvas: TemplateCanvas, path: Optional[str] = None):
        self.canvas = canvas
        self.view.setScene(canvas)
        canvas.selectionChanged.connect(self.on_selection_changed)
        canvas.document_changed.connect(self._mark_dirty)
        self.preview_data = {}
        self.excel_table = None
        self.excel_profile = None
        self.current_path = path
        self.is_dirty = False
        self.undo_stack.clear()
        if path:
            self._remember_file(path)
        self._set_document_actions_enabled(True)
        self._update_window_title()

    def _recent_files(self):
        return self.settings.value("recent_files", [], type=list)

    def _remember_file(self, path: str):
        files = [path] + [entry for entry in self._recent_files() if entry != path]
        self.settings.setValue("recent_files", files[:8])
        if hasattr(self, "recent_menu"):
            self._refresh_recent_menu()

    def _refresh_recent_menu(self):
        self.recent_menu.clear()
        files = [path for path in self._recent_files() if path]
        if not files:
            empty = QAction("Aucun fichier récent", self)
            empty.setEnabled(False)
            self.recent_menu.addAction(empty)
            return
        for path in files:
            action = QAction(path, self)
            action.triggered.connect(lambda checked=False, value=path: self._open_path(value))
            self.recent_menu.addAction(action)

    def _open_path(self, path: str):
        if not self._confirm_document_change():
            return
        try:
            with open(path, "r", encoding="utf-8") as file:
                template = LabelTemplate.from_json(file.read())
            canvas = TemplateCanvas(template)
            self._set_canvas(canvas, path)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir le gabarit : {error}")

    def _write_autosave(self):
        if not self.canvas or not self.is_dirty:
            return
        try:
            self.settings.setValue("autosave_template", self.canvas.serialize_current_template())
            self.settings.setValue("autosave_path", self.current_path or "")
        except ValueError:
            pass

    def _restore_autosave(self):
        autosave = self.settings.value("autosave_template", "", type=str)
        if not autosave:
            return
        choice = QMessageBox.question(
            self,
            "Récupération disponible",
            "Une récupération automatique du dernier document est disponible. La restaurer ?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if choice != QMessageBox.Yes:
            self.settings.remove("autosave_template")
            return
        try:
            self._set_canvas(TemplateCanvas(LabelTemplate.from_json(autosave)))
            self.is_dirty = True
            self._update_window_title()
        except (ValueError, TypeError, KeyError, AttributeError):
            self.settings.remove("autosave_template")

    def on_file_new_gabarit(self):
        """Action File -> New -> New Gabarit."""
        if not self._confirm_document_change():
            return
        dialog = NewGabaritDialog(self)
        if dialog.exec() == NewGabaritDialog.Accepted:
            template = dialog.get_template()
            if errors := template.validate():
                QMessageBox.warning(self, "Gabarit invalide", "\n".join(errors))
                return
            
            # Instanciation du Canvas uniquement APRÈS la définition du gabarit
            self._set_canvas(TemplateCanvas(template))

    def on_selection_changed(self):
        if not self.canvas: return
        selected = [item for item in self.canvas.selectedItems() if isinstance(item, BaseLabelItem)]
        self.inspector.set_selected_items(selected)
        self.act_copy.setEnabled(bool(selected))
        self.act_duplicate.setEnabled(bool(selected))
        self.act_delete.setEnabled(bool(selected))

    def on_delete_selected(self):
        if self.canvas:
            self._run_canvas_edit("Supprimer", self.canvas.delete_selected_items)

    def on_duplicate_selected(self):
        if self.canvas:
            self._run_canvas_edit("Dupliquer", self.canvas.duplicate_selected_items)

    def on_copy_selected(self):
        if not self.canvas:
            return
        selected = [item.to_dict() for item in self.canvas.selectedItems() if isinstance(item, BaseLabelItem)]
        if selected:
            QApplication.clipboard().setText(json.dumps(selected))

    def on_paste_selected(self):
        if not self.canvas:
            return
        try:
            records = json.loads(QApplication.clipboard().text())
            if not isinstance(records, list):
                return
        except (json.JSONDecodeError, TypeError):
            return

        def paste_items():
            self.canvas.clearSelection()
            pasted = 0
            for record in records:
                if not isinstance(record, dict) or "type" not in record:
                    continue
                data = dict(record)
                prefix = str(data.get("id", "item")).rsplit("_", 1)[0]
                data["id"] = self.canvas.next_item_id(prefix)
                data["x_mm"] = float(data.get("x_mm", 0)) + 5
                data["y_mm"] = float(data.get("y_mm", 0)) + 5
                item = BaseLabelItem.from_dict(data, self.canvas.scale)
                self.canvas.addItem(item)
                item.setSelected(True)
                pasted += 1
            return pasted

        self._run_canvas_edit("Coller", paste_items)

    def _run_canvas_edit(self, text, operation):
        if not self.canvas:
            return 0
        before = self.canvas.item_snapshot()
        result = operation()
        after = self.canvas.item_snapshot()
        if before != after:
            self.undo_stack.push(SnapshotCommand(self.canvas, before, after, text))
        return result

    def on_align(self, mode):
        if self.canvas:
            self._run_canvas_edit("Aligner", lambda: self.canvas.align_items(mode))

    def on_distribute(self, direction):
        if self.canvas:
            self._run_canvas_edit("Distribuer", lambda: self.canvas.distribute_items(direction))

    def on_toggle_preview(self, enabled: bool):
        if self.canvas:
            self.canvas.set_preview_data(self.preview_data, enabled)

    def on_add_tier_item(self):
        if not self.canvas: return
        def add_item():
            item = TierPriceLabelItem(
                self.canvas.next_item_id("tier"), x_mm=10, y_mm=10,
                scale_px_per_mm=self.canvas.scale
            )
            self.canvas.addItem(item)
            item.setSelected(True)
            return 1
        self._run_canvas_edit("Ajouter bloc palier", add_item)

    def on_add_rich_item(self, rich_type: str):
        """Create a selectable editor adapter for a rich render item."""
        if not self.canvas:
            return
        if rich_type == "image":
            path, _ = QFileDialog.getOpenFileName(
                self, "Choisir une image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
            )
            if not path:
                return
        else:
            path = None

        def add_item():
            item = RichLabelItem.create(
                rich_type,
                self.canvas.next_item_id(rich_type),
                scale_px_per_mm=self.canvas.scale,
            )
            if path:
                item.rich_item.source = path
            self.canvas.addItem(item)
            item.setSelected(True)
            return 1
        self._run_canvas_edit("Ajouter objet", add_item)

    def on_add_domain_field(self, field_name: str):
        if not self.canvas:
            return
        def add_item():
            item = DomainFieldLabelItem.create_field(
                field_name, self.canvas.next_item_id("field"), self.canvas.scale,
            )
            self.canvas.addItem(item)
            item.setSelected(True)
            return 1
        self._run_canvas_edit("Ajouter champ métier", add_item)

    def on_validate_bounds(self):
        if not self.canvas: return
        faulty = self.canvas.validate_item_bounds()
        if faulty:
            QMessageBox.warning(self, "Avertissement", f"{len(faulty)} objet(s) dépassent la zone imprimable (bandes clignotantes affichées).")
        else:
            QMessageBox.information(self, "Validation", "Tous les objets sont correctement positionnés.")

    def _confirm_document_change(self) -> bool:
        """Ask whether the current document should be saved before replacement."""
        if not self.is_dirty:
            return True

        choice = QMessageBox.question(
            self,
            "Modifications non sauvegardées",
            "Enregistrer les modifications avant de continuer ?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
        )
        if choice == QMessageBox.Save:
            return self.on_file_save()
        return choice == QMessageBox.Discard

    def on_file_save(self) -> bool:
        if not self.canvas:
            QMessageBox.critical(self, "Erreur", "Aucun gabarit actif à sauvegarder.")
            return False

        path = self.current_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Sauvegarder Gabarit JSON", "", "JSON (*.json)")
            if not path:
                return False
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            json_str = self.canvas.finalize_and_save_template()
            with open(path, "w", encoding="utf-8") as f:
                f.write(json_str)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Erreur", f"Impossible de sauvegarder le gabarit : {error}")
            return False
        self.current_path = path
        self.is_dirty = False
        self._remember_file(path)
        self.settings.remove("autosave_template")
        self._update_window_title()
        excluded = len(self.canvas.last_validation_report)
        message = "Gabarit sauvegardé."
        if excluded:
            message += f" {excluded} objet(s) hors-limites ont été exclus automatiquement."
        QMessageBox.information(self, "Succès", message)
        self.document_saved.emit(path, LabelTemplate.from_json(json_str))
        return True

    def on_load_preview_data(self):
        if not self.canvas:
            return
        dialog = PreviewDataDialog(self.preview_data, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self.preview_data = dialog.values()
        self.act_preview.setEnabled(bool(self.preview_data))
        self.act_preview.setChecked(bool(self.preview_data))
        self.canvas.set_preview_data(self.preview_data, bool(self.preview_data))
        QMessageBox.information(self, "Données chargées", f"{len(self.preview_data)} champ(s) seront appliqués à l'export PNG.")

    def on_import_excel(self):
        if not self.canvas:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importer un classeur Excel",
            "",
            "Excel (*.xlsx *.xlsm)",
        )
        if not path:
            return
        try:
            table = read_xlsx(path)
            if len(table.rows) == 0:
                raise WorkbookReadError("La feuille sélectionnée ne contient aucune ligne de données.")
            suggestions = suggest_mappings(table.headers)
            mapping_dialog = MappingDialog(table.headers, suggestions, self)
            if mapping_dialog.exec() != QDialog.Accepted:
                return
            profile = mapping_dialog.profile()
            if errors := profile.validate(set(table.headers)):
                raise ValueError("Mapping invalide : " + "; ".join(errors))
            self.excel_table = table
            self.excel_profile = profile
            self.act_export_excel.setEnabled(True)
            self.act_export_excel_pages.setEnabled(True)
            if len(table.rows) > 1:
                row_number, accepted = QInputDialog.getInt(
                    self,
                    "Ligne d'aperçu",
                    f"Numéro de ligne Excel ({table.rows[0].row_number}-{table.rows[-1].row_number}) :",
                    table.rows[0].row_number,
                    table.rows[0].row_number,
                    table.rows[-1].row_number,
                )
                if not accepted:
                    return
                row = next((item for item in table.rows if item.row_number == row_number), table.rows[0])
            else:
                row = table.rows[0]

            result = normalize_row(row, profile)
            self.preview_data = result.record
            self.act_preview.setEnabled(bool(self.preview_data))
            self.act_preview.setChecked(bool(self.preview_data))
            self.canvas.set_preview_data(self.preview_data, bool(self.preview_data))
            warnings = table.issues + result.issues
            message = f"Ligne {row.row_number} importée : {len(self.preview_data)} champ(s)."
            if warnings:
                message += "\n\n" + "\n".join(issue.message for issue in warnings[:8])
            QMessageBox.information(self, "Import Excel", message)
        except (OSError, ValueError, TypeError, WorkbookReadError) as error:
            QMessageBox.critical(self, "Erreur d'import Excel", str(error))

    def on_export_excel(self):
        if not self.canvas or self.excel_table is None or self.excel_profile is None:
            return
        output_directory = QFileDialog.getExistingDirectory(self, "Dossier de sortie Excel")
        if not output_directory:
            return
        options = ExportOptionsDialog(parent=self)
        if options.exec() != QDialog.Accepted:
            return
        try:
            report = self._normalize_excel_in_background()
            if report is None:
                return
            progress = QProgressDialog("Export des lignes Excel…", "Annuler", 0, len(report.results), self)
            progress.setWindowTitle("Export Excel")
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            report = export_rows_as_png(
                self.canvas,
                report,
                output_directory,
                options.dpi.value(),
                lambda current, total: self._update_export_progress(progress, current, total),
            )
            progress.close()
            report_path = str(Path(output_directory) / "export_report.json")
            with open(report_path, "w", encoding="utf-8") as file:
                file.write(report.to_json())
            QMessageBox.information(
                self,
                "Export Excel terminé",
                f"{report.succeeded} fichier(s) exporté(s), {report.failed} ligne(s) en erreur.\nRapport : {report_path}",
            )
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Erreur d'export Excel", str(error))

    @staticmethod
    def _update_export_progress(progress, current: int, total: int) -> bool:
        progress.setMaximum(max(1, total))
        progress.setValue(current)
        QApplication.processEvents()
        return not progress.wasCanceled()

    def on_export_excel_pages(self):
        if not self.canvas or self.excel_table is None or self.excel_profile is None:
            return
        output_directory = QFileDialog.getExistingDirectory(self, "Dossier de sortie des feuilles")
        if not output_directory:
            return
        options = ExportOptionsDialog(page=True, parent=self)
        if options.exec() != QDialog.Accepted:
            return
        try:
            report = self._normalize_excel_in_background()
            if report is None:
                return
            progress = QProgressDialog("Composition des feuilles Excel…", "Annuler", 0, len(report.results), self)
            progress.setWindowTitle("Export Excel")
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            report = export_rows_on_pages(
                self.canvas,
                report,
                output_directory,
                options.page_size.currentText(),
                options.gap.value(),
                options.dpi.value(),
                lambda current, total: self._update_export_progress(progress, current, total),
            )
            progress.close()
            report_path = str(Path(output_directory) / "export_report.json")
            with open(report_path, "w", encoding="utf-8") as file:
                file.write(report.to_json())
            QMessageBox.information(self, "Export feuilles terminé", f"{report.succeeded} ligne(s) exportée(s), {report.failed} erreur(s).\nRapport : {report_path}")
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Erreur d'export feuilles", str(error))

    def _normalize_excel_in_background(self):
        progress = QProgressDialog("Lecture et validation des lignes Excel…", "Annuler", 0, 0, self)
        progress.setWindowTitle("Import Excel")
        progress.setWindowModality(Qt.WindowModal)
        thread = QThread(self)
        worker = ExcelNormalizeWorker(None, self.excel_profile, table=self.excel_table)
        worker.moveToThread(thread)
        result = {"report": None, "error": None}
        loop = QEventLoop(self)

        def on_progress(current, total):
            progress.setMaximum(max(1, total))
            progress.setValue(current)
            QApplication.processEvents()

        def on_finished(_table, report):
            result["report"] = report
            loop.quit()

        def on_failed(message):
            result["error"] = message
            loop.quit()

        progress.canceled.connect(worker.cancel)
        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        thread.started.connect(worker.run)
        thread.finished.connect(worker.deleteLater)
        thread.start()
        progress.show()
        loop.exec()
        progress.close()
        worker.cancel()
        thread.quit()
        thread.wait()
        if result["error"]:
            raise ValueError(result["error"])
        if progress.wasCanceled():
            return None
        return result["report"]

    def on_export_png(self):
        if not self.canvas:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter l'étiquette PNG", "", "PNG (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        options = ExportOptionsDialog(parent=self)
        if options.exec() != QDialog.Accepted:
            return
        try:
            self.canvas.export_png(path, dpi=options.dpi.value(), data_record=self.preview_data)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Erreur", f"Impossible d'exporter le PNG : {error}")
            return
        QMessageBox.information(self, "Export terminé", f"Étiquette exportée en PNG à {options.dpi.value():g} DPI.")

    def on_export_page_png(self):
        if not self.canvas:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter la feuille A4", "", "PNG (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        options = ExportOptionsDialog(page=True, parent=self)
        if options.exec() != QDialog.Accepted:
            return
        try:
            self.canvas.export_page_png(
                path,
                page_size_name=options.page_size.currentText(),
                gap_mm=options.gap.value(),
                dpi=options.dpi.value(),
                data_record=self.preview_data,
            )
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Erreur", f"Impossible d'exporter la feuille : {error}")
            return
        QMessageBox.information(self, "Export terminé", f"Feuille {options.page_size.currentText()} exportée en PNG.")

    def on_file_open(self):
        if not self._confirm_document_change():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir Gabarit JSON", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as file:
                template = LabelTemplate.from_json(file.read())
            canvas = TemplateCanvas(template)
            self._set_canvas(canvas, path)
            if canvas.load_warnings:
                QMessageBox.warning(
                    self,
                    "Éléments ignorés",
                    f"{len(canvas.load_warnings)} élément(s) n'ont pas pu être chargés. "
                    "Le document peut être réparé puis sauvegardé.",
                )
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir le gabarit : {error}")

    def closeEvent(self, event: QCloseEvent):
        if not self.is_dirty:
            event.accept()
            return
        choice = QMessageBox.question(
            self,
            "Modifications non sauvegardées",
            "Les modifications actuelles seront perdues. Fermer quand même ?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
        )
        if choice == QMessageBox.Save:
            event.accept() if self.on_file_save() else event.ignore()
        elif choice == QMessageBox.Discard:
            event.accept()
        else:
            event.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = EditorMainWindow()
    win.show()
    sys.exit(app.exec())
