"""Application principale orchestrant la création, l'édition et la sauvegarde."""

import json
import sys
from typing import Any, Dict, Optional
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QDockWidget, 
    QToolBar, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence

from gabarit_wizard import NewGabaritDialog
from template_canvas import TemplateCanvas
from template_model import LabelTemplate
from property_inspector import PropertyInspectorWidget
from label_items import BaseLabelItem, RichLabelItem, TierPriceLabelItem


class EditorMainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Concepteur de Gabarits d'Étiquettes & Paliers")
        self.resize(1200, 800)

        self.canvas: Optional[TemplateCanvas] = None
        self.preview_data: Dict[str, Any] = {}
        self.view = QGraphicsView(self)
        self.setCentralWidget(self.view)

        # Dock latéral
        self.inspector = PropertyInspectorWidget(self)
        dock = QDockWidget("Inspecteur de Propriétés", self)
        dock.setWidget(self.inspector)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

        self._build_menus_and_toolbars()

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

        self.act_load_preview_data = QAction("Charger données d'aperçu…", self)
        self.act_load_preview_data.setEnabled(False)
        self.act_load_preview_data.triggered.connect(self.on_load_preview_data)
        file_menu.addAction(self.act_load_preview_data)

        self.act_export_png = QAction("Exporter PNG…", self)
        self.act_export_png.setEnabled(False)
        self.act_export_png.triggered.connect(self.on_export_png)
        file_menu.addAction(self.act_export_png)

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

        self.act_validate = QAction("Contrôler Dépassements", self)
        self.act_validate.setEnabled(False)
        self.act_validate.triggered.connect(self.on_validate_bounds)
        toolbar.addAction(self.act_validate)

    def _set_document_actions_enabled(self, enabled: bool):
        self.act_add_tier.setEnabled(enabled)
        self.act_validate.setEnabled(enabled)
        self.act_export_png.setEnabled(enabled)
        self.act_load_preview_data.setEnabled(enabled)
        for action in self.rich_actions:
            action.setEnabled(enabled)

    def on_file_new_gabarit(self):
        """Action File -> New -> New Gabarit."""
        dialog = NewGabaritDialog(self)
        if dialog.exec() == NewGabaritDialog.Accepted:
            template = dialog.get_template()
            if errors := template.validate():
                QMessageBox.warning(self, "Gabarit invalide", "\n".join(errors))
                return
            
            # Instanciation du Canvas uniquement APRÈS la définition du gabarit
            self.canvas = TemplateCanvas(template)
            self.view.setScene(self.canvas)
            self.canvas.selectionChanged.connect(self.on_selection_changed)

            self.preview_data = {}
            self._set_document_actions_enabled(True)

    def on_selection_changed(self):
        if not self.canvas: return
        selected = [item for item in self.canvas.selectedItems() if isinstance(item, BaseLabelItem)]
        self.inspector.set_selected_items(selected)

    def on_add_tier_item(self):
        if not self.canvas: return
        item = TierPriceLabelItem(
            self.canvas.next_item_id("tier"), x_mm=10, y_mm=10,
            scale_px_per_mm=self.canvas.scale
        )
        self.canvas.addItem(item)
        item.setSelected(True)

    def on_add_rich_item(self, rich_type: str):
        """Create a selectable editor adapter for a rich render item."""
        if not self.canvas:
            return
        item = RichLabelItem.create(
            rich_type,
            self.canvas.next_item_id(rich_type),
            scale_px_per_mm=self.canvas.scale,
        )
        if rich_type == "image":
            path, _ = QFileDialog.getOpenFileName(
                self, "Choisir une image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
            )
            if path:
                item.rich_item.source = path
        self.canvas.addItem(item)
        item.setSelected(True)

    def on_validate_bounds(self):
        if not self.canvas: return
        faulty = self.canvas.validate_item_bounds()
        if faulty:
            QMessageBox.warning(self, "Avertissement", f"{len(faulty)} objet(s) dépassent la zone imprimable (bandes clignotantes affichées).")
        else:
            QMessageBox.information(self, "Validation", "Tous les objets sont correctement positionnés.")

    def on_file_save(self):
        if not self.canvas:
            QMessageBox.critical(self, "Erreur", "Aucun gabarit actif à sauvegarder.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Sauvegarder Gabarit JSON", "", "JSON (*.json)")
        if not path:
            return
        try:
            json_str = self.canvas.finalize_and_save_template()
            with open(path, "w", encoding="utf-8") as f:
                f.write(json_str)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Erreur", f"Impossible de sauvegarder le gabarit : {error}")
            return
        QMessageBox.information(self, "Succès", "Gabarit sauvegardé. Les objets hors-limites ont été automatiquement exclus.")

    def on_load_preview_data(self):
        if not self.canvas:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Charger les données d'aperçu", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, dict):
                raise ValueError("Le fichier de données doit contenir un objet JSON.")
            self.preview_data = data
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Erreur", f"Impossible de charger les données : {error}")
            return
        QMessageBox.information(self, "Données chargées", f"{len(self.preview_data)} champ(s) seront appliqués à l'export PNG.")

    def on_export_png(self):
        if not self.canvas:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter l'étiquette PNG", "", "PNG (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            self.canvas.export_png(path, data_record=self.preview_data)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Erreur", f"Impossible d'exporter le PNG : {error}")
            return
        QMessageBox.information(self, "Export terminé", "Étiquette exportée en PNG à 300 DPI.")

    def on_file_open(self):
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir Gabarit JSON", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as file:
                template = LabelTemplate.from_json(file.read())
            self.canvas = TemplateCanvas(template)
            self.view.setScene(self.canvas)
            self.canvas.selectionChanged.connect(self.on_selection_changed)
            self.preview_data = {}
            self._set_document_actions_enabled(True)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir le gabarit : {error}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = EditorMainWindow()
    win.show()
    sys.exit(app.exec())
