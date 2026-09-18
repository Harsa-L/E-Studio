"""Dedicated gabarit editor window used by both Home and Generation routes."""

from PySide6.QtCore import Signal

from ui.main_window import EditorMainWindow
from core.models.template_model import LabelTemplate


class TemplateEditorWindow(EditorMainWindow):
    """Named editor boundary kept separate from the generation workspace."""

    document_saved = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__()
        if parent is not None:
            self.setParent(parent, self.windowFlags())
        self.setWindowTitle("Éditeur de gabarit")

    def on_file_save(self) -> bool:
        saved = super().on_file_save()
        if saved and self.canvas is not None:
            self.document_saved.emit(self.current_path or "", self.canvas.template)
        return saved