"""Application principale orchestrant la création, l'édition et la sauvegarde."""

import sys
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
from label_items import BaseLabelItem, TierPriceLabelItem


class EditorMainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Concepteur de Gabarits d'Étiquettes & Paliers")
        self.resize(1200, 800)

        self.canvas: TemplateCanvas = None
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

        # Barre d'outils
        toolbar = QToolBar("Actions")
        self.addToolBar(toolbar)

        self.act_add_tier = QAction("Ajouter Bloc Palier", self)
        self.act_add_tier.setEnabled(False)
        self.act_add_tier.triggered.connect(self.on_add_tier_item)
        toolbar.addAction(self.act_add_tier)

        self.act_validate = QAction("Contrôler Dépassements", self)
        self.act_validate.setEnabled(False)
        self.act_validate.triggered.connect(self.on_validate_bounds)
        toolbar.addAction(self.act_validate)

    def on_file_new_gabarit(self):
        """Action File -> New -> New Gabarit."""
        dialog = NewGabaritDialog(self)
        if dialog.exec() == NewGabaritDialog.Accepted:
            template = dialog.get_template()
            
            # Instanciation du Canvas uniquement APRÈS la définition du gabarit
            self.canvas = TemplateCanvas(template)
            self.view.setScene(self.canvas)
            self.canvas.selectionChanged.connect(self.on_selection_changed)

            self.act_add_tier.setEnabled(True)
            self.act_validate.setEnabled(True)

    def on_selection_changed(self):
        if not self.canvas: return
        selected = [item for item in self.canvas.selectedItems() if isinstance(item, BaseLabelItem)]
        self.inspector.set_selected_items(selected)

    def on_add_tier_item(self):
        if not self.canvas: return
        item = TierPriceLabelItem(
            f"tier_{len(self.canvas.items())}", x_mm=10, y_mm=10,
            scale_px_per_mm=self.canvas.scale
        )
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
            self.act_add_tier.setEnabled(True)
            self.act_validate.setEnabled(True)
        except (OSError, ValueError, TypeError, KeyError) as error:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir le gabarit : {error}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = EditorMainWindow()
    win.show()
    sys.exit(app.exec())