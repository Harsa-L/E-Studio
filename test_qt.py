"""Offscreen Qt regression checks for editor item persistence."""

import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from main import EditorMainWindow
from label_items import DomainFieldLabelItem, RichLabelItem
from batch_export import BatchRowResult, BatchReport, export_rows_on_pages
from template_editor_window import TemplateEditorWindow
from template_canvas import TemplateCanvas
from template_model import LabelTemplate, Margins
from rich_text_models import SizingMode


class RichItemPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_text_layout_state_round_trip(self) -> None:
        item = RichLabelItem.create("text", "text_1")
        text = item.rich_item
        text.margins = tuple(value + offset for value, offset in zip(text.margins, (1, 2, 3, 4)))
        text.sizing_mode = SizingMode.LOCKED
        text.line_spacing_reduction = 0.25
        text.font_scale = 0.75
        text.border_style = text.border_style.DashLine

        restored = RichLabelItem.from_dict(item.to_dict())
        restored_text = restored.rich_item

        self.assertEqual(tuple(float(value) for value in restored_text.margins), tuple(float(value) for value in text.margins))
        self.assertEqual(restored_text.sizing_mode, SizingMode.LOCKED)
        self.assertEqual(restored_text.line_spacing_reduction, 0.25)
        self.assertEqual(restored_text.font_scale, 0.75)
        self.assertEqual(restored_text.border_style, text.border_style)

    def test_export_uses_physical_dimensions_and_preserves_binding_source(self) -> None:
        template = LabelTemplate(
            name="Export",
            width_mm=25.4,
            height_mm=12.7,
            inner_margins_mm=Margins(0, 0, 0, 0),
            outer_margins_mm=Margins(0, 0, 0, 0),
        )
        canvas = TemplateCanvas(template)
        item = RichLabelItem.create("text", "text_1", w_mm=20, h_mm=8)
        item.rich_item.binding_key = "NAME"
        canvas.addItem(item)
        original_text = item.rich_item.plain_text()
        canvas.set_preview_data({"NAME": "Preview"})

        with tempfile.NamedTemporaryFile(suffix=".png") as output:
            canvas.export_png(output.name, dpi=300)
            image = QImage(output.name)

        self.assertEqual((image.width(), image.height()), (300, 150))
        self.assertEqual(image.dotsPerMeterX(), round(300 / 0.0254))
        self.assertEqual(item.rich_item.plain_text(), original_text)

    def test_duplicate_and_delete_selected_items(self) -> None:
        template = LabelTemplate(
            name="Editing",
            width_mm=50,
            height_mm=50,
            inner_margins_mm=Margins(0, 0, 0, 0),
            outer_margins_mm=Margins(0, 0, 0, 0),
        )
        canvas = TemplateCanvas(template)
        item = RichLabelItem.create("shape", "shape_1")
        canvas.addItem(item)
        item.setSelected(True)

        self.assertEqual(canvas.duplicate_selected_items(), 1)
        self.assertEqual(len([entry for entry in canvas.items() if isinstance(entry, RichLabelItem)]), 2)
        for entry in canvas.items():
            entry.setSelected(True)
        self.assertEqual(canvas.delete_selected_items(), 2)
        self.assertEqual(len(canvas.items()), 0)

    def test_page_export_uses_selected_sheet_size(self) -> None:
        template = LabelTemplate(
            name="Sheet",
            width_mm=50,
            height_mm=40,
            inner_margins_mm=Margins(0, 0, 0, 0),
            outer_margins_mm=Margins(2, 2, 2, 2),
        )
        canvas = TemplateCanvas(template)

        with tempfile.NamedTemporaryFile(suffix=".png") as output:
            canvas.export_page_png(output.name, page_size_name="A4", dpi=25.4)
            image = QImage(output.name)

        self.assertEqual((image.width(), image.height()), (210, 297))

    def test_alignment_and_snapshot_restore(self) -> None:
        template = LabelTemplate(
            name="Alignment",
            width_mm=100,
            height_mm=50,
            inner_margins_mm=Margins(0, 0, 0, 0),
            outer_margins_mm=Margins(0, 0, 0, 0),
        )
        canvas = TemplateCanvas(template)
        first = RichLabelItem.create("shape", "shape_1", x_mm=5, y_mm=5, w_mm=10, h_mm=5)
        second = RichLabelItem.create("shape", "shape_2", x_mm=30, y_mm=12, w_mm=10, h_mm=5)
        canvas.addItem(first)
        canvas.addItem(second)
        first.setSelected(True)
        second.setSelected(True)

        snapshot = canvas.item_snapshot()
        self.assertEqual(canvas.align_items("left"), 2)
        self.assertEqual(first.get_x_mm(), second.get_x_mm())
        canvas.restore_item_snapshot(snapshot)
        restored = {item.item_id: item for item in canvas.items() if isinstance(item, RichLabelItem)}
        self.assertEqual(restored["shape_1"].get_x_mm(), 5.0)
        self.assertEqual(restored["shape_2"].get_x_mm(), 30.0)

    def test_batch_page_export_creates_imposed_sheet(self) -> None:
        template = LabelTemplate(
            name="Batch",
            width_mm=25.4,
            height_mm=12.7,
            inner_margins_mm=Margins(0, 0, 0, 0),
            outer_margins_mm=Margins(0, 0, 0, 0),
        )
        canvas = TemplateCanvas(template)
        canvas.addItem(RichLabelItem.create("text", "text_1", w_mm=20, h_mm=8))
        report = BatchReport([
            BatchRowResult(2, {"NAME": "A"}, []),
            BatchRowResult(3, {"NAME": "B"}, []),
        ])

        with tempfile.TemporaryDirectory() as directory:
            exported = export_rows_on_pages(canvas, report, directory, "A4", dpi=25.4)
            image = QImage(os.path.join(directory, "sheet_001.png"))

        self.assertEqual(exported.succeeded, 2)
        self.assertFalse(image.isNull())

    def test_template_editor_exposes_save_signal(self) -> None:
        template = LabelTemplate(
            name="Editor",
            width_mm=20,
            height_mm=20,
            inner_margins_mm=Margins(0, 0, 0, 0),
            outer_margins_mm=Margins(0, 0, 0, 0),
        )
        editor = TemplateEditorWindow()
        received = []
        editor.document_saved.connect(lambda path, saved: received.append((path, saved.name)))
        editor._set_canvas(TemplateCanvas(template), "/tmp/editor.json")
        editor.document_saved.emit("/tmp/editor.json", editor.canvas.template)

        self.assertEqual(received, [("/tmp/editor.json", "Editor")])

    def test_specialized_domain_field_round_trip(self) -> None:
        item = DomainFieldLabelItem.create_field("ITEMNAME", "field_1")

        restored = DomainFieldLabelItem.from_dict(item.to_dict())

        self.assertEqual(restored.domain_field, "ITEMNAME")
        self.assertEqual(restored.rich_item.binding_key, "ITEMNAME")

    def test_save_reuses_existing_document_path(self) -> None:
        template = LabelTemplate(
            name="Save",
            width_mm=25.0,
            height_mm=25.0,
            inner_margins_mm=Margins(0, 0, 0, 0),
            outer_margins_mm=Margins(0, 0, 0, 0),
        )
        window = EditorMainWindow()
        with tempfile.NamedTemporaryFile(suffix=".json") as output:
            window._set_canvas(TemplateCanvas(template), output.name)
            window.is_dirty = True
            with patch("main.QFileDialog.getSaveFileName") as choose_path, patch(
                "main.QMessageBox.information"
            ):
                self.assertTrue(window.on_file_save())

            choose_path.assert_not_called()
            self.assertFalse(window.is_dirty)
            self.assertIn('"name": "Save"', output.read().decode("utf-8"))
        window.close()


if __name__ == "__main__":
    unittest.main()