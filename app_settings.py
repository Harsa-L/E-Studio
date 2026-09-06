"""Typed application policies used by the home and generation workflows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TemplateDiscoveryMode(str, Enum):
    FOLDER_AND_RECENT = "folder_and_recent"
    MANAGED_LIBRARY = "managed_library"


class GenerationEditPolicy(str, Enum):
    FREEZE_SNAPSHOT = "freeze_snapshot"
    RESTART_GENERATION = "restart_generation"


class BindingObjectMode(str, Enum):
    SPECIALIZED = "specialized"
    GENERIC = "generic"


class PreviewMode(str, Enum):
    LIVE = "live"
    DELAYED = "delayed"
    MANUAL = "manual"


class OutputPriority(str, Enum):
    PRINTER = "printer"
    PDF = "pdf"


@dataclass(frozen=True)
class AppSettings:
    """Stable, serializable policy defaults for the two-route application."""

    discovery_mode: TemplateDiscoveryMode = TemplateDiscoveryMode.FOLDER_AND_RECENT
    template_folder: str = ""
    generation_edit_policy: GenerationEditPolicy = GenerationEditPolicy.FREEZE_SNAPSHOT
    binding_object_mode: BindingObjectMode = BindingObjectMode.SPECIALIZED
    preview_mode: PreviewMode = PreviewMode.DELAYED
    output_priority: OutputPriority = OutputPriority.PRINTER
    diagnostics_timing: str = "during"
    confirm_tier_grouping: bool = True
    allow_pdf_output: bool = True

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.diagnostics_timing not in {"before", "during", "after"}:
            errors.append("Diagnostics timing must be before, during, or after.")
        if not isinstance(self.confirm_tier_grouping, bool):
            errors.append("Tier grouping confirmation must be boolean.")
        if not isinstance(self.allow_pdf_output, bool):
            errors.append("PDF output availability must be boolean.")
        return errors

    def to_dict(self) -> dict[str, Any]:
        if errors := self.validate():
            raise ValueError("Invalid application settings: " + "; ".join(errors))
        return {
            "discovery_mode": self.discovery_mode.value,
            "template_folder": self.template_folder,
            "generation_edit_policy": self.generation_edit_policy.value,
            "binding_object_mode": self.binding_object_mode.value,
            "preview_mode": self.preview_mode.value,
            "output_priority": self.output_priority.value,
            "diagnostics_timing": self.diagnostics_timing,
            "confirm_tier_grouping": self.confirm_tier_grouping,
            "allow_pdf_output": self.allow_pdf_output,
        }

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "AppSettings":
        try:
            settings = cls(
                discovery_mode=TemplateDiscoveryMode(values.get("discovery_mode", cls.discovery_mode.value)),
                template_folder=str(values.get("template_folder", "")),
                generation_edit_policy=GenerationEditPolicy(values.get("generation_edit_policy", cls.generation_edit_policy.value)),
                binding_object_mode=BindingObjectMode(values.get("binding_object_mode", cls.binding_object_mode.value)),
                preview_mode=PreviewMode(values.get("preview_mode", cls.preview_mode.value)),
                output_priority=OutputPriority(values.get("output_priority", cls.output_priority.value)),
                diagnostics_timing=str(values.get("diagnostics_timing", "during")),
                confirm_tier_grouping=bool(values.get("confirm_tier_grouping", True)),
                allow_pdf_output=bool(values.get("allow_pdf_output", True)),
            )
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid application settings: {error}") from error
        if errors := settings.validate():
            raise ValueError("Invalid application settings: " + "; ".join(errors))
        return settings
