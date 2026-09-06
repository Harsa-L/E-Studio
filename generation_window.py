"""Protected generation workspace built from an immutable template snapshot."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QSignalBlocker
from PySide6.QtWidgets import (
    QFileDialog, QGraphicsView, QHBoxLayout, QLabel, QListWidget,
    QMainWindow, QMessageBox, QPushButton, QVBoxLayout, QWidget, QInputDialog,
    QTableWidget, QTableWidgetItem, QComboBox, QDialog, QDialogButtonBox,
)

from generation_session import GenerationSession, TemplateSnapshot
from template_canvas import TemplateCanvas
from data_sources import ImportedRow, WorkbookReadError, read_xlsx
from data_normalization import normalize_row
from binding_profiles import BindingProfile, suggest_mappings
from batch_export import BatchReport, BatchRowResult, export_rows_as_png, export_rows_on_pages, normalize_workbook
from data_sources import ImportIssue
from tier_grouping import TierGroupingConfig, normalize_grouped_articles
from output_service import OutputService
from template_editor_window import TemplateEditorWindow
from app_settings import GenerationEditPolicy
from main import ExportOptionsDialog, MappingDialog


class PreflightDialog(QDialog):
    def __init__(self, report: BatchReport, issues, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Prévalidation avant génération")
        self.resize(760, 420)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"Articles valides : {report.succeeded} | Articles bloqués : {report.failed} | "
            f"Diagnostics : {len(issues)}"
        ))
        self.table = QTableWidget(len(issues), 4, self)
        self.table.setHorizontalHeaderLabels(["Sévérité", "Code", "Source", "Message"])
        self.table.horizontalHeader().setStretchLastSection(True)
        for row, issue in enumerate(issues):
            self.table.setItem(row, 0, QTableWidgetItem(issue.severity))
            self.table.setItem(row, 1, QTableWidgetItem(issue.code))
            source = f"{issue.sheet}:{issue.row_number}" if issue.sheet else ""
            self.table.setItem(row, 2, QTableWidgetItem(source))
            self.table.setItem(row, 3, QTableWidgetItem(issue.message))
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No)
        buttons.button(QDialogButtonBox.Yes).setText("Continuer avec les lignes valides")
        buttons.button(QDialogButtonBox.No).setText("Annuler")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class GenerationWindow(QMainWindow):
    """Generation route; the active gabarit is intentionally read-only here."""

    def __init__(self, snapshot: TemplateSnapshot, parent=None):
        super().__init__(parent)
        self.session = GenerationSession(snapshot)
        self.setWindowTitle(f"Génération — {snapshot.name}")
        self.resize(1100, 760)
        self.canvas = TemplateCanvas(snapshot.load())
        self.preview = self.canvas
        self.excel_table = None
        self.excel_profile: BindingProfile | None = None
        self.grouping_config: TierGroupingConfig | None = None
        self.batch_report: BatchReport | None = None
        self.editor_windows = []
        self.settings = QSettings("E-Studio", "E-Studio")
        self._updating_source_table = False
        self._all_issues = []
        self.source_issues = []

        root = QWidget(self)
        layout = QVBoxLayout(root)
        header = QHBoxLayout()
        header.addWidget(QLabel(f"Gabarit verrouillé : {snapshot.name}"))
        self.edit_button = QPushButton("Modifier le gabarit")
        self.edit_button.clicked.connect(self.edit_template_requested)
        header.addWidget(self.edit_button)
        self.import_button = QPushButton("Importer Excel")
        self.import_button.clicked.connect(self.import_excel)
        header.addWidget(self.import_button)
        self.export_button = QPushButton("Exporter PNG")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_rows)
        header.addWidget(self.export_button)
        self.pages_button = QPushButton("Exporter feuilles")
        self.pages_button.setEnabled(False)
        self.pages_button.clicked.connect(self.export_pages)
        header.addWidget(self.pages_button)
        self.pdf_button = QPushButton("Exporter PDF")
        self.pdf_button.setEnabled(False)
        self.pdf_button.clicked.connect(self.export_pdf)
        header.addWidget(self.pdf_button)
        self.print_button = QPushButton("Imprimer")
        self.print_button.setEnabled(False)
        self.print_button.clicked.connect(self.print_label)
        header.addWidget(self.print_button)
        self.print_preview_button = QPushButton("Aperçu impression")
        self.print_preview_button.setEnabled(False)
        self.print_preview_button.clicked.connect(self.print_preview)
        header.addWidget(self.print_preview_button)
        self.previous_button = QPushButton("Précédent")
        self.previous_button.setEnabled(False)
        self.previous_button.clicked.connect(self.select_previous)
        header.addWidget(self.previous_button)
        self.next_button = QPushButton("Suivant")
        self.next_button.setEnabled(False)
        self.next_button.clicked.connect(self.select_next)
        header.addWidget(self.next_button)
        self.refresh_preview_button = QPushButton("Actualiser aperçu")
        self.refresh_preview_button.clicked.connect(self.refresh_preview)
        header.addWidget(self.refresh_preview_button)
        self.save_profile_button = QPushButton("Enregistrer profil")
        self.save_profile_button.setEnabled(False)
        self.save_profile_button.clicked.connect(self.save_profile)
        header.addWidget(self.save_profile_button)
        self.load_profile_button = QPushButton("Charger profil")
        self.load_profile_button.clicked.connect(self.load_profile)
        header.addWidget(self.load_profile_button)
        layout.addLayout(header)
        layout.addWidget(QLabel("Cette génération utilise une copie immuable du gabarit sélectionné."))
        source_header = QHBoxLayout()
        source_header.addWidget(QLabel("Données importées et modifiables"))
        self.add_row_button = QPushButton("Ajouter")
        self.add_row_button.setEnabled(False)
        self.add_row_button.clicked.connect(self.add_source_row)
        source_header.addWidget(self.add_row_button)
        self.remove_row_button = QPushButton("Supprimer")
        self.remove_row_button.setEnabled(False)
        self.remove_row_button.clicked.connect(self.remove_source_rows)
        source_header.addWidget(self.remove_row_button)
        self.duplicate_row_button = QPushButton("Dupliquer")
        self.duplicate_row_button.setEnabled(False)
        self.duplicate_row_button.clicked.connect(self.duplicate_source_row)
        source_header.addWidget(self.duplicate_row_button)
        self.reprocess_button = QPushButton("Recalculer")
        self.reprocess_button.setEnabled(False)
        self.reprocess_button.clicked.connect(self.reprocess_source)
        source_header.addWidget(self.reprocess_button)
        layout.addLayout(source_header)
        self.source_table = QTableWidget(0, 0, self)
        self.source_table.itemChanged.connect(self._source_cell_changed)
        self.source_table.itemSelectionChanged.connect(self._update_source_actions)
        layout.addWidget(self.source_table, 2)
        self.preview_view = QGraphicsView(self)
        self.preview_view.setScene(self.canvas)
        layout.addWidget(self.preview_view, 3)
        self.rows = QListWidget()
        self.rows.currentRowChanged.connect(self.select_row)
        layout.addWidget(QLabel("Lignes source"))
        layout.addWidget(self.rows, 1)
        self.diagnostics = QListWidget()
        diagnostics_header = QHBoxLayout()
        diagnostics_header.addWidget(QLabel("Diagnostics"))
        self.diagnostics_filter = QComboBox()
        self.diagnostics_filter.addItem("Toutes", "all")
        self.diagnostics_filter.addItem("Erreurs", "error")
        self.diagnostics_filter.addItem("Avertissements", "warning")
        self.diagnostics_filter.currentIndexChanged.connect(self._show_diagnostics)
        diagnostics_header.addWidget(self.diagnostics_filter)
        layout.addLayout(diagnostics_header)
        layout.addWidget(self.diagnostics)
        self.setCentralWidget(root)
        self._refresh_diagnostics()

    def edit_template_requested(self):
        editor = TemplateEditorWindow(self)
        self.editor_windows.append(editor)
        editor.document_saved.connect(self._editor_saved)
        editor.show()
        if self.session.template_snapshot.source_path:
            editor._open_path(self.session.template_snapshot.source_path)
        else:
            editor.on_file_new_gabarit()
        self._refresh_diagnostics()

    def _editor_saved(self, path: str, template):
        snapshot = TemplateSnapshot.from_template(template, path)
        policy = self.settings.value(
            "generation_edit_policy",
            GenerationEditPolicy.FREEZE_SNAPSHOT.value,
            type=str,
        )
        self.apply_edited_snapshot(
            snapshot,
            restart=policy == GenerationEditPolicy.RESTART_GENERATION.value,
        )

    def import_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importer un classeur Excel", "", "Excel (*.xlsx *.xlsm)")
        if not path:
            return
        try:
            table = read_xlsx(path)
            if not table.rows:
                raise WorkbookReadError("La feuille sélectionnée est vide.")
            suggestions = suggest_mappings(table.headers)
            saved_profile_json = self.settings.value(f"binding_profile::{path}", "", type=str)
            if saved_profile_json:
                try:
                    saved_profile = BindingProfile.from_json(saved_profile_json)
                    if not saved_profile.validate(set(table.headers)):
                        for mapping in saved_profile.mappings:
                            suggestions[mapping.source_column] = mapping.target_key
                            suggestions[f"{mapping.source_column}:type"] = mapping.field_type
                except (ValueError, TypeError):
                    pass
            mapping_dialog = MappingDialog(table.headers, suggestions, self)
            if mapping_dialog.exec() != mapping_dialog.Accepted:
                return
            profile = mapping_dialog.profile()
            if errors := profile.validate(set(table.headers)):
                raise ValueError("Mapping invalide : " + "; ".join(errors))
            key, accepted = QInputDialog.getItem(
                self,
                "Regroupement des articles",
                "Colonne identifiant l'article :",
                table.headers,
                0,
                False,
            )
            if not accepted:
                return
            conflict_policy, accepted = QInputDialog.getItem(
                self,
                "Prix de palier en conflit",
                "Politique de résolution :",
                ["Signaler et bloquer", "Choisir le prix le plus bas", "Garder la première valeur"],
                0,
                False,
            )
            if not accepted:
                return
            policy = {"Signaler et bloquer": "report", "Choisir le prix le plus bas": "lowest_price", "Garder la première valeur": "first"}[conflict_policy]
            self.grouping_config = TierGroupingConfig(article_key=key, conflict_policy=policy)
            self.excel_table = table
            self.excel_profile = profile
            self.source_issues = list(table.issues)
            self.settings.setValue(f"binding_profile::{path}", profile.to_json())
            self._populate_source_table()
            self.reprocess_source()
            self.export_button.setEnabled(True)
            self.pages_button.setEnabled(True)
            self.pdf_button.setEnabled(True)
            self.print_button.setEnabled(True)
            self.print_preview_button.setEnabled(True)
            self.pdf_button.setEnabled(self.settings.value("allow_pdf_output", True, type=bool))
            self.add_row_button.setEnabled(True)
            self.reprocess_button.setEnabled(True)
            self.save_profile_button.setEnabled(True)
            self.settings.setValue("last_grouping_key", key)
            self._add_issues(table.issues)
        except (OSError, ValueError, TypeError, WorkbookReadError) as error:
            QMessageBox.critical(self, "Erreur d'import", str(error))

    def select_row(self, index: int):
        if self.batch_report is None or index < 0:
            return
        result = self.batch_report.results[index]
        if result.record is None:
            return
        issues = [*result.issues, *self._binding_issues(result.record)]
        self._add_issues(issues)
        if self.settings.value("preview_mode", "delayed", type=str) == "manual":
            return
        self.canvas.set_preview_data(result.record, result.valid)

    def refresh_preview(self):
        if self.batch_report is None or self.rows.currentRow() < 0:
            return
        result = self.batch_report.results[self.rows.currentRow()]
        if result.record is not None:
            self.canvas.set_preview_data(result.record, result.valid)

    def _binding_issues(self, record):
        issues = []
        for item in self.canvas.items():
            binding_key = None
            if hasattr(item, "rich_item"):
                binding_key = item.rich_item.binding_key
            elif item.__class__.__name__ == "TierPriceLabelItem":
                if "TIERS" not in record:
                    issues.append(ImportIssue("missing_tiers", "Le gabarit utilise des paliers mais aucune structure TIERS n'est disponible.", "warning"))
            if binding_key and binding_key not in record:
                issues.append(ImportIssue("missing_binding", f"La clé de binding {binding_key!r} est absente de la ligne.", "warning"))
        return issues

    def select_previous(self):
        self.rows.setCurrentRow(max(0, self.rows.currentRow() - 1))

    def select_next(self):
        self.rows.setCurrentRow(min(self.rows.count() - 1, self.rows.currentRow() + 1))

    def _populate_source_table(self):
        if self.excel_table is None:
            return
        self._updating_source_table = True
        blocker = QSignalBlocker(self.source_table)
        self.source_table.setColumnCount(len(self.excel_table.headers))
        self.source_table.setHorizontalHeaderLabels(self.excel_table.headers)
        self.source_table.setRowCount(len(self.excel_table.rows))
        for row_index, row in enumerate(self.excel_table.rows):
            for column_index, header in enumerate(self.excel_table.headers):
                self.source_table.setItem(row_index, column_index, QTableWidgetItem(self._display_value(row.raw_values.get(header))))
        del blocker
        self._updating_source_table = False
        self.source_table.resizeColumnsToContents()

    @staticmethod
    def _display_value(value):
        return "" if value is None else str(value)

    def _source_cell_changed(self, _item):
        if not self._updating_source_table:
            self.reprocess_source()

    def _update_source_actions(self):
        has_selection = bool(self.source_table.selectedIndexes())
        self.remove_row_button.setEnabled(has_selection)
        self.duplicate_row_button.setEnabled(has_selection)

    def _sync_source_table(self):
        if self.excel_table is None:
            return
        rows = []
        for row_index in range(self.source_table.rowCount()):
            values = {
                header: self.source_table.item(row_index, column_index).text()
                if self.source_table.item(row_index, column_index) else ""
                for column_index, header in enumerate(self.excel_table.headers)
            }
            original_row_number = self.excel_table.rows[row_index].row_number if row_index < len(self.excel_table.rows) else row_index + 2
            rows.append(ImportedRow(self.excel_table.sheet, original_row_number, dict(values), dict(values)))
        self.excel_table.rows = rows

    def add_source_row(self):
        if self.excel_table is None:
            return
        self.source_table.insertRow(self.source_table.rowCount())
        for column_index in range(self.source_table.columnCount()):
            self.source_table.setItem(self.source_table.rowCount() - 1, column_index, QTableWidgetItem(""))
        self._sync_source_table()
        self.reprocess_source()

    def remove_source_rows(self):
        selected = sorted({index.row() for index in self.source_table.selectedIndexes()}, reverse=True)
        for row_index in selected:
            self.source_table.removeRow(row_index)
        if selected:
            self._sync_source_table()
            self.reprocess_source()

    def duplicate_source_row(self):
        selected = self.source_table.currentRow()
        if selected < 0:
            return
        target = self.source_table.rowCount()
        self.source_table.insertRow(target)
        for column_index in range(self.source_table.columnCount()):
            source = self.source_table.item(selected, column_index)
            self.source_table.setItem(target, column_index, QTableWidgetItem(source.text() if source else ""))
        self._sync_source_table()
        self.reprocess_source()

    def reprocess_source(self):
        if self.excel_table is None or self.excel_profile is None or self.grouping_config is None:
            return
        self._sync_source_table()
        grouped = normalize_grouped_articles(self.excel_table.rows, self.excel_profile, self.grouping_config)
        self.batch_report = BatchReport([
            BatchRowResult(row_number, record, issues)
            for record, issues, row_number in grouped
        ])
        self.rows.blockSignals(True)
        self.rows.clear()
        for record, issues, row_number in grouped:
            article_key = next(
                (row.raw_values.get(self.grouping_config.article_key, "?")
                 for row in self.excel_table.rows if row.row_number == row_number),
                "?",
            )
            self.rows.addItem(f"{article_key} — ligne {row_number}")
        self.rows.blockSignals(False)
        self.next_button.setEnabled(bool(grouped))
        self.previous_button.setEnabled(bool(grouped))
        self.remove_row_button.setEnabled(bool(self.source_table.rowCount()))
        if grouped:
            self.rows.setCurrentRow(0)
        issues = list(self.source_issues)
        for result in self.batch_report.results:
            issues.extend(result.issues)
            if result.record is not None:
                issues.extend(self._binding_issues(result.record))
        self._add_issues(issues)

    def _normalized_report(self):
        if self.batch_report is not None:
            return self.batch_report
        if self.excel_table is None or self.excel_profile is None:
            return None
        return normalize_workbook(self.excel_table, self.excel_profile, "skip_invalid_rows")

    def _add_issues(self, issues):
        self._all_issues = list(issues)
        self._show_diagnostics()

    def _show_diagnostics(self):
        selected = self.diagnostics_filter.currentData() if hasattr(self, "diagnostics_filter") else "all"
        self.diagnostics.clear()
        for issue in self._all_issues:
            if selected != "all" and issue.severity != selected:
                continue
            location = f" [{issue.sheet}:{issue.row_number}]" if issue.sheet else ""
            self.diagnostics.addItem(f"{issue.code}{location}: {issue.message}")

    def export_rows(self):
        report = self._normalized_report()
        if report is None:
            return
        if not self._confirm_preflight(report):
            return
        directory = QFileDialog.getExistingDirectory(self, "Dossier de sortie")
        if not directory:
            return
        options = ExportOptionsDialog(parent=self)
        if options.exec() != options.Accepted:
            return
        try:
            result = export_rows_as_png(self.canvas, report, directory, options.dpi.value())
            self._add_issues([issue for row in result.results for issue in row.issues])
            result.write_manifest(str(Path(directory) / "export_manifest.json"), directory, "png")
            QMessageBox.information(self, "Export terminé", f"{result.succeeded} étiquette(s) exportée(s), {result.failed} erreur(s).")
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Erreur d'export", str(error))

    def export_pages(self):
        report = self._normalized_report()
        if report is None:
            return
        if not self._confirm_preflight(report):
            return
        directory = QFileDialog.getExistingDirectory(self, "Dossier de sortie des feuilles")
        if not directory:
            return
        options = ExportOptionsDialog(page=True, parent=self)
        if options.exec() != options.Accepted:
            return
        try:
            result = export_rows_on_pages(
                self.canvas,
                report,
                directory,
                options.page_size.currentText(),
                options.gap.value(),
                options.dpi.value(),
            )
            self._add_issues([issue for row in result.results for issue in row.issues])
            result.write_manifest(str(Path(directory) / "export_manifest.json"), directory, "imposed_png")
            QMessageBox.information(self, "Export terminé", f"{result.succeeded} ligne(s) exportée(s), {result.failed} erreur(s).")
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Erreur d'export", str(error))

    def _selected_record(self):
        if self.batch_report is None or self.rows.currentRow() < 0:
            return None
        result = self.batch_report.results[self.rows.currentRow()]
        return result.record if result.valid else None

    def _confirm_preflight(self, report: BatchReport) -> bool:
        issues = [issue for result in report.results for issue in result.issues]
        for result in report.results:
            if result.record is not None:
                issues.extend(self._binding_issues(result.record))
        errors = sum(issue.severity == "error" for issue in issues)
        warnings = sum(issue.severity == "warning" for issue in issues)
        if not errors and not warnings:
            return True
        dialog = PreflightDialog(report, issues, self)
        return dialog.exec() == QDialog.Accepted

    def save_profile(self):
        if self.excel_profile is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer le profil", "", "Profil JSON (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            with open(path, "w", encoding="utf-8") as file:
                file.write(self.excel_profile.to_json())
            self.settings.setValue("last_binding_profile", path)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Erreur", f"Impossible d'enregistrer le profil : {error}")

    def load_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, "Charger le profil", "", "Profil JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as file:
                profile = BindingProfile.from_json(file.read())
            if self.excel_table is not None:
                if errors := profile.validate(set(self.excel_table.headers)):
                    raise ValueError("Profil incompatible : " + "; ".join(errors))
                self.excel_profile = profile
                self.reprocess_source()
            else:
                self.excel_profile = profile
            self.settings.setValue("last_binding_profile", path)
            self.save_profile_button.setEnabled(self.excel_table is not None)
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Erreur", f"Impossible de charger le profil : {error}")

    def export_pdf(self):
        record = self._selected_record()
        if record is None:
            QMessageBox.warning(self, "Aucune donnée", "Sélectionnez une ligne valide avant l'export PDF.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter en PDF", "", "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            OutputService.export_pdf(self.canvas, path, data_record=record)
            QMessageBox.information(self, "Export terminé", "Étiquette PDF exportée.")
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Erreur PDF", str(error))

    def print_label(self):
        record = self._selected_record()
        if record is None:
            QMessageBox.warning(self, "Aucune donnée", "Sélectionnez une ligne valide avant l'impression.")
            return
        if QMessageBox.question(self, "Confirmer l'impression", "Envoyer cette étiquette à l'imprimante ?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            OutputService.print_label(self.canvas, self, record)
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Erreur d'impression", str(error))

    def print_preview(self):
        record = self._selected_record()
        if record is None:
            QMessageBox.warning(self, "Aucune donnée", "Sélectionnez une ligne valide avant l'aperçu.")
            return
        OutputService.print_preview(self.canvas, self, record)

    def apply_edited_snapshot(self, snapshot: TemplateSnapshot, restart: bool = False):
        self.session.apply_editor_result(snapshot, restart=restart)
        if restart:
            self.canvas = TemplateCanvas(snapshot.load())
            self.preview = self.canvas
        self._refresh_diagnostics()

    def _refresh_diagnostics(self):
        self.diagnostics.clear()
        for diagnostic in self.session.diagnostics:
            self.diagnostics.addItem(f"{diagnostic['code']} : {diagnostic['message']}")
