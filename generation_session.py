"""Immutable template snapshots and protected generation session state."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import json

from template_model import LabelTemplate


class GenerationState(str, Enum):
    CREATED = "created"
    PREPARING = "preparing"
    PREVIEWING = "previewing"
    GENERATING = "generating"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class TemplateSnapshot:
    """Serialized copy used by generation; editor mutations cannot affect it."""

    name: str
    serialized_template: str
    source_path: str | None = None

    @classmethod
    def from_template(cls, template: LabelTemplate, source_path: str | None = None) -> "TemplateSnapshot":
        return cls(template.name, template.to_json(), source_path)

    def load(self) -> LabelTemplate:
        return LabelTemplate.from_json(self.serialized_template)


@dataclass
class GenerationSession:
    template_snapshot: TemplateSnapshot
    state: GenerationState = GenerationState.CREATED
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    generated_count: int = 0
    failed_count: int = 0

    def set_state(self, state: GenerationState) -> None:
        self.state = state

    def add_diagnostic(self, code: str, message: str, **context: Any) -> None:
        self.diagnostics.append({"code": code, "message": message, **context})

    def apply_editor_result(self, snapshot: TemplateSnapshot, restart: bool = False) -> None:
        if not restart:
            self.add_diagnostic("template_edit_pending", "A new gabarit version is available; current generation remains on its original snapshot.", source_path=snapshot.source_path)
            return
        if self.state in {GenerationState.GENERATING, GenerationState.COMPLETED}:
            raise RuntimeError("The generation must be stopped before restarting with an edited template.")
        self.template_snapshot = snapshot
        self.state = GenerationState.CREATED
        self.generated_count = 0
        self.failed_count = 0
        self.add_diagnostic("template_replaced", "Generation restarted with the edited gabarit.", source_path=snapshot.source_path)
