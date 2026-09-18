"""General settings dialog for the two-route workflow."""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit

from core.settings.app_settings import (
    AppSettings,
    BindingObjectMode,
    GenerationEditPolicy,
    OutputPriority,
    PreviewMode,
    TemplateDiscoveryMode,
)


class SettingsWindow(QDialog):
    def __init__(self, parent=None, settings_store: QSettings | None = None):
        super().__init__(parent)
        self.setWindowTitle("Paramètres généraux")
        self.resize(560, 420)
        self.settings_store = settings_store or QSettings("E-Studio", "E-Studio")
        current = self.load_settings()
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignRight)
        form.setContentsMargins(18, 18, 18, 18)
        form.setSpacing(12)

        self.discovery_mode = QComboBox()
        self.discovery_mode.addItem("Dossier + récents", TemplateDiscoveryMode.FOLDER_AND_RECENT.value)
        self.discovery_mode.addItem("Bibliothèque gérée", TemplateDiscoveryMode.MANAGED_LIBRARY.value)
        self.discovery_mode.setCurrentIndex(self.discovery_mode.findData(current.discovery_mode.value))
        form.addRow("Découverte des gabarits", self.discovery_mode)

        self.template_folder = QLineEdit(current.template_folder)
        form.addRow("Dossier des gabarits", self.template_folder)

        self.edit_policy = QComboBox()
        self.edit_policy.addItem("Geler la génération", GenerationEditPolicy.FREEZE_SNAPSHOT.value)
        self.edit_policy.addItem("Redémarrer après modification", GenerationEditPolicy.RESTART_GENERATION.value)
        self.edit_policy.setCurrentIndex(self.edit_policy.findData(current.generation_edit_policy.value))
        form.addRow("Modification pendant génération", self.edit_policy)

        self.binding_mode = QComboBox()
        self.binding_mode.addItem("Objets spécialisés", BindingObjectMode.SPECIALIZED.value)
        self.binding_mode.addItem("Objets génériques", BindingObjectMode.GENERIC.value)
        self.binding_mode.setCurrentIndex(self.binding_mode.findData(current.binding_object_mode.value))
        form.addRow("Objets de données", self.binding_mode)

        self.preview_mode = QComboBox()
        for label, value in (("Temps réel", PreviewMode.LIVE.value), ("Différé", PreviewMode.DELAYED.value), ("Manuel", PreviewMode.MANUAL.value)):
            self.preview_mode.addItem(label, value)
        self.preview_mode.setCurrentIndex(self.preview_mode.findData(current.preview_mode.value))
        form.addRow("Aperçu", self.preview_mode)

        self.output_priority = QComboBox()
        self.output_priority.addItem("Imprimante", OutputPriority.PRINTER.value)
        self.output_priority.addItem("PDF", OutputPriority.PDF.value)
        self.output_priority.setCurrentIndex(self.output_priority.findData(current.output_priority.value))
        form.addRow("Sortie principale", self.output_priority)

        self.diagnostics_timing = QComboBox()
        for label, value in (("Avant génération", "before"), ("Pendant génération", "during"), ("Après génération", "after")):
            self.diagnostics_timing.addItem(label, value)
        self.diagnostics_timing.setCurrentIndex(self.diagnostics_timing.findData(current.diagnostics_timing))
        form.addRow("Diagnostics", self.diagnostics_timing)

        self.confirm_tiers = QCheckBox("Demander confirmation")
        self.confirm_tiers.setChecked(current.confirm_tier_grouping)
        form.addRow("Regroupement des paliers", self.confirm_tiers)
        self.allow_pdf = QCheckBox("Autoriser la sortie PDF")
        self.allow_pdf.setChecked(current.allow_pdf_output)
        form.addRow("PDF", self.allow_pdf)

        self.boundary_warning_enabled = QCheckBox("Alerte live hors limites")
        self.boundary_warning_enabled.setChecked(current.boundary_warning_enabled)
        form.addRow("Alerte limite", self.boundary_warning_enabled)

        self.boundary_warning_color = QLineEdit(current.boundary_warning_color)
        form.addRow("Couleur alerte", self.boundary_warning_color)

        self.boundary_warning_flash_ms = QLineEdit(str(current.boundary_warning_flash_ms))
        form.addRow("Flash (ms)", self.boundary_warning_flash_ms)

        self.boundary_warning_style = QComboBox()
        for label, value in (("Contour", "outline"), ("Remplissage", "fill"), ("Les deux", "both")):
            self.boundary_warning_style.addItem(label, value)
        self.boundary_warning_style.setCurrentIndex(self.boundary_warning_style.findData(current.boundary_warning_style))
        form.addRow("Style d'alerte", self.boundary_warning_style)

        self.boundary_tolerance_mm = QLineEdit(str(current.boundary_tolerance_mm))
        form.addRow("Tolérance (mm)", self.boundary_tolerance_mm)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Enregistrer")
        buttons.button(QDialogButtonBox.Cancel).setText("Annuler")
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def load_settings(self) -> AppSettings:
        values = {key: self.settings_store.value(key, default) for key, default in AppSettings().to_dict().items()}
        return AppSettings.from_dict(values)

    def values(self) -> AppSettings:
        try:
            tolerance = float(self.boundary_tolerance_mm.text())
        except ValueError:
            tolerance = 0.0
        try:
            flash_ms = int(self.boundary_warning_flash_ms.text())
        except ValueError:
            flash_ms = 250
        return AppSettings.from_dict({
            "discovery_mode": self.discovery_mode.currentData(),
            "template_folder": self.template_folder.text().strip(),
            "generation_edit_policy": self.edit_policy.currentData(),
            "binding_object_mode": self.binding_mode.currentData(),
            "preview_mode": self.preview_mode.currentData(),
            "output_priority": self.output_priority.currentData(),
            "diagnostics_timing": self.diagnostics_timing.currentData(),
            "confirm_tier_grouping": self.confirm_tiers.isChecked(),
            "allow_pdf_output": self.allow_pdf.isChecked(),
            "boundary_warning_enabled": self.boundary_warning_enabled.isChecked(),
            "boundary_warning_color": self.boundary_warning_color.text().strip() or "#ef4444",
            "boundary_warning_flash_ms": flash_ms,
            "boundary_warning_style": self.boundary_warning_style.currentData(),
            "boundary_tolerance_mm": tolerance,
        })

    def _save_and_accept(self):
        for key, value in self.values().to_dict().items():
            self.settings_store.setValue(key, value)
        self.accept()
