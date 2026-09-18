"""Command objects for the application layer.

The UI emits commands; the service layer executes them. This keeps the Qt layer
from directly owning domain logic or model mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class NewTemplateCommand:
    name: str = "Nouveau gabarit"
    path: str | None = None


@dataclass(frozen=True)
class OpenTemplateCommand:
    path: str


@dataclass(frozen=True)
class SaveTemplateCommand:
    path: str | None = None
    content: str | None = None


@dataclass(frozen=True)
class ExportTemplateCommand:
    path: str
    dpi: int = 300
    page_size: str = "A4"
    gap_mm: float = 0.0
    preview_data: dict[str, Any] | None = None


@dataclass(frozen=True)
class BuildWorkspaceStateCommand:
    mode: str = "home"
