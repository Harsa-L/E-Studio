"""Immutable template snapshots and protected generation session state."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.models.business_model import GenerationReadiness, TemplateBusinessProfile
from core.models.template_model import LabelTemplate


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


@dataclass(frozen=True)
class BusinessDecision:
    """Formal business-state contract for a generation session."""

    state: GenerationState
    can_import: bool
    can_preview: bool
    can_export: bool
    can_edit: bool
    has_blockers: bool
    is_template_ready: bool
    readiness: GenerationReadiness | None = None


@dataclass
class GenerationSession:
    template_snapshot: TemplateSnapshot
    state: GenerationState = GenerationState.CREATED
    workflow_state: str = "created"
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    generated_count: int = 0
    failed_count: int = 0
    business_profile: TemplateBusinessProfile | None = None
    readiness: GenerationReadiness | None = None

    def __post_init__(self) -> None:
        self.refresh_business_state()

    VALID_TRANSITIONS: dict[GenerationState, set[GenerationState]] = field(
        default_factory=lambda: {
            GenerationState.CREATED: {GenerationState.CREATED, GenerationState.PREPARING, GenerationState.CANCELLED},
            GenerationState.PREPARING: {GenerationState.PREPARING, GenerationState.PREVIEWING, GenerationState.CANCELLED},
            GenerationState.PREVIEWING: {GenerationState.PREVIEWING, GenerationState.GENERATING, GenerationState.PREPARING, GenerationState.CANCELLED},
            GenerationState.GENERATING: {GenerationState.GENERATING, GenerationState.COMPLETED, GenerationState.CANCELLED},
            GenerationState.COMPLETED: {GenerationState.COMPLETED},
            GenerationState.CANCELLED: {GenerationState.CANCELLED},
        }
    )

    @classmethod
    def _canonical_state(cls, value: str) -> GenerationState:
        normalized = value.strip().lower()
        aliases = {
            "ready": GenerationState.CREATED,
            "created": GenerationState.CREATED,
            "preparing": GenerationState.PREPARING,
            "previewing": GenerationState.PREVIEWING,
            "generating": GenerationState.GENERATING,
            "completed": GenerationState.COMPLETED,
            "cancelled": GenerationState.CANCELLED,
        }
        if normalized not in aliases:
            raise ValueError(f"Unsupported workflow state: {value!r}")
        return aliases[normalized]

    def set_state(self, state: GenerationState | str) -> None:
        if isinstance(state, str):
            self.transition_to(state)
            return
        self.transition_to(state.value)

    def transition_to(self, workflow_state: str) -> None:
        target_state = self._canonical_state(workflow_state)
        if self.state == target_state:
            self.workflow_state = target_state.value
            return
        allowed = self.VALID_TRANSITIONS.get(self.state, set())
        if target_state not in allowed:
            raise ValueError(
                f"Invalid workflow transition from '{self.state.value}' to '{target_state.value}'."
            )
        self.state = target_state
        self.workflow_state = target_state.value

    def can_transition_to(self, workflow_state: str) -> bool:
        try:
            target_state = self._canonical_state(workflow_state)
        except ValueError:
            return False
        return target_state in self.VALID_TRANSITIONS.get(self.state, set()) or self.state == target_state

    def refresh_business_state(self) -> None:
        template = self.template_snapshot.load()
        self.business_profile = TemplateBusinessProfile.from_template(template)
        self.readiness = GenerationReadiness.from_template(template)
        if self.readiness.blockers:
            self.diagnostics = [
                {"code": "template_ready", "message": "; ".join(self.readiness.blockers), "severity": "error"}
            ]
        elif self.readiness.warnings:
            self.diagnostics = [
                {"code": "template_warning", "message": "; ".join(self.readiness.warnings), "severity": "warning"}
            ]

    def is_template_ready(self) -> bool:
        return bool(self.readiness and self.readiness.is_ready)

    def business_decision(self) -> BusinessDecision:
        template_ready = self.is_template_ready()
        read_only_states = {GenerationState.GENERATING, GenerationState.COMPLETED}
        previewable_states = {GenerationState.PREVIEWING, GenerationState.GENERATING, GenerationState.COMPLETED}
        decision = BusinessDecision(
            state=self.state,
            can_import=template_ready and self.state not in read_only_states,
            can_preview=template_ready and self.state in previewable_states,
            can_export=template_ready and self.state in previewable_states,
            can_edit=self.state not in read_only_states,
            has_blockers=bool(self.readiness and self.readiness.blockers),
            is_template_ready=template_ready,
            readiness=self.readiness,
        )
        return decision

    def available_actions(self) -> dict[str, bool]:
        decision = self.business_decision()
        return {
            "edit_template": decision.can_edit,
            "import_excel": decision.can_import,
            "export_png": decision.can_export,
            "export_pages": decision.can_export,
            "export_pdf": decision.can_export,
            "print": decision.can_export,
            "preview": decision.can_preview,
            "source_edit": decision.can_import,
            "save_profile": decision.can_import,
        }

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
        self.workflow_state = "created"
        self.generated_count = 0
        self.failed_count = 0
        self.refresh_business_state()
        self.add_diagnostic("template_replaced", "Generation restarted with the edited gabarit.", source_path=snapshot.source_path)
