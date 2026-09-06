"""File-based template discovery for the home screen."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from template_model import LabelTemplate


@dataclass(frozen=True)
class TemplateSummary:
    path: str
    name: str | None
    width_mm: float | None
    height_mm: float | None
    valid: bool
    error: str | None = None


class TemplateLibrary:
    """Index JSON gabarits from configured folders and recent paths."""

    def __init__(self, folder: str | Path | None = None, recent_paths: Iterable[str] = (), managed_paths: Iterable[str] = ()):
        self.folder = Path(folder).expanduser() if folder else None
        self.recent_paths = list(dict.fromkeys(str(path) for path in recent_paths))
        self.managed_paths = list(dict.fromkeys(str(path) for path in managed_paths))

    def discover(self) -> list[TemplateSummary]:
        paths: list[Path] = []
        if self.folder and self.folder.exists():
            paths.extend(sorted(self.folder.glob("*.json")))
        paths.extend(Path(path).expanduser() for path in self.recent_paths)
        paths.extend(Path(path).expanduser() for path in self.managed_paths)
        summaries: list[TemplateSummary] = []
        seen: set[str] = set()
        for path in paths:
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            summaries.append(self._read_summary(path))
        return summaries

    @staticmethod
    def _read_summary(path: Path) -> TemplateSummary:
        try:
            with path.open("r", encoding="utf-8") as source:
                template = LabelTemplate.from_json(source.read())
            return TemplateSummary(str(path), template.name, template.width_mm, template.height_mm, True)
        except (OSError, ValueError, TypeError, KeyError) as error:
            return TemplateSummary(str(path), None, None, None, False, str(error))
