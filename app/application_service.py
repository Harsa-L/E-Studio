"""Application service layer: commands and state transitions for the UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.models.template_model import LabelTemplate
from core.models.template_library import TemplateLibrary
from core.rendering.template_canvas import TemplateCanvas
from core.settings.app_settings import TemplateDiscoveryMode
from core.workflows.generation_session import TemplateSnapshot


@dataclass(frozen=True)
class TemplateSummaryState:
    path: str
    name: str
    valid: bool
    error: str | None = None


@dataclass(frozen=True)
class WorkspaceState:
    templates: list[TemplateSummaryState]
    status: str = "Workspace ready"


class AppService:
    """Pure Python application service that the UI can call through commands and signals."""

    def __init__(self, settings: Any | None = None):
        self.settings = settings

    def discover_templates(self) -> list[TemplateSummaryState]:
        folder = self.settings.value("template_folder", "", type=str) if self.settings else ""
        recent = self.settings.value("recent_files", [], type=list) if self.settings else []
        managed = self.settings.value("managed_templates", [], type=list) if self.settings else []
        mode = self.settings.value("discovery_mode", TemplateDiscoveryMode.FOLDER_AND_RECENT.value, type=str) if self.settings else TemplateDiscoveryMode.FOLDER_AND_RECENT.value
        library = TemplateLibrary(folder or None, recent, managed)
        if mode == TemplateDiscoveryMode.MANAGED_LIBRARY.value:
            library = TemplateLibrary(None, [], managed)
        return [
            TemplateSummaryState(
                path=str(summary.path),
                name=summary.name or Path(summary.path).name,
                valid=bool(summary.valid),
                error=summary.error,
            )
            for summary in library.discover()
        ]

    def load_template(self, path: str) -> LabelTemplate:
        with open(path, "r", encoding="utf-8") as source:
            return LabelTemplate.from_json(source.read())

    def snapshot_template(self, path: str) -> TemplateSnapshot:
        template = self.load_template(path)
        return TemplateSnapshot.from_template(template, path)

    def add_to_library(self, path: str) -> None:
        if not self.settings:
            return
        managed = self.settings.value("managed_templates", [], type=list)
        self.settings.setValue("managed_templates", list(dict.fromkeys([*managed, path])))

    def open_template_file(self, path: str) -> str:
        return Path(path).name

    def create_canvas(self, template: LabelTemplate) -> TemplateCanvas:
        return TemplateCanvas(template)

    def load_canvas(self, path: str) -> TemplateCanvas:
        with open(path, "r", encoding="utf-8") as source:
            template = LabelTemplate.from_json(source.read())
        return TemplateCanvas(template)

    def save_canvas(self, canvas: TemplateCanvas, path: str) -> str:
        json_text = canvas.finalize_and_save_template()
        with open(path, "w", encoding="utf-8") as target:
            target.write(json_text)
        return json_text
