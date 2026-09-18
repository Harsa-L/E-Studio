"""Business-first model for template geometry, readiness, and generation policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.models.template_model import LabelTemplate, Margins


@dataclass(frozen=True)
class PrintableArea:
    """Normalized printable area and safety envelope for a label template."""

    width_mm: float
    height_mm: float
    x_margin_mm: float
    y_margin_mm: float
    safe_zone_mm: float


@dataclass(frozen=True)
class TemplateBusinessProfile:
    """Business-level description of a template's printable geometry and readiness."""

    name: str
    width_mm: float
    height_mm: float
    inner_margins_mm: Margins
    outer_margins_mm: Margins
    printable_width_mm: float
    printable_height_mm: float
    safe_zone_mm: float
    item_count: int
    layout_kind: str
    layout_mode: str
    is_generation_ready: bool
    validation_errors: tuple[str, ...] = ()

    @property
    def printable_area(self) -> PrintableArea:
        return PrintableArea(
            width_mm=self.printable_width_mm,
            height_mm=self.printable_height_mm,
            x_margin_mm=self.inner_margins_mm.left + self.inner_margins_mm.right,
            y_margin_mm=self.inner_margins_mm.top + self.inner_margins_mm.bottom,
            safe_zone_mm=self.safe_zone_mm,
        )

    @property
    def complexity(self) -> int:
        return max(1, self.item_count // 2)

    @classmethod
    def from_template(cls, template: LabelTemplate) -> "TemplateBusinessProfile":
        errors = tuple(template.validate())
        inner = template.inner_margins_mm
        printable_width = template.width_mm - inner.left - inner.right
        printable_height = template.height_mm - inner.top - inner.bottom
        safe_zone = max(
            10.0,
            min(
                max(inner.top, 0.0),
                max(inner.bottom, 0.0),
                max(inner.left, 0.0),
                max(inner.right, 0.0),
            )
            * 0.5,
        )
        return cls(
            name=template.name,
            width_mm=template.width_mm,
            height_mm=template.height_mm,
            inner_margins_mm=inner,
            outer_margins_mm=template.outer_margins_mm,
            printable_width_mm=printable_width,
            printable_height_mm=printable_height,
            safe_zone_mm=safe_zone,
            item_count=len(template.items),
            layout_kind=template.layout_kind,
            layout_mode=template.layout_mode,
            is_generation_ready=not errors,
            validation_errors=errors,
        )


@dataclass(frozen=True)
class GenerationReadiness:
    """Formal business readiness contract for the generation pipeline."""

    is_ready: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    business_profile: TemplateBusinessProfile

    @classmethod
    def from_template(cls, template: LabelTemplate) -> "GenerationReadiness":
        profile = TemplateBusinessProfile.from_template(template)
        blockers = tuple(profile.validation_errors)
        warnings: tuple[str, ...] = ()
        if profile.printable_width_mm < 20.0 or profile.printable_height_mm < 20.0:
            warnings += ("Printable area is very small for multi-item composition.",)
        if profile.item_count == 0:
            warnings += ("Template contains no printable items yet.",)
        return cls(
            is_ready=profile.is_generation_ready and not blockers,
            blockers=blockers,
            warnings=warnings,
            business_profile=profile,
        )


def summarize_template_geo(template: LabelTemplate) -> dict[str, float | int | bool | str | tuple[str, ...]]:
    profile = TemplateBusinessProfile.from_template(template)
    return {
        "name": profile.name,
        "width_mm": profile.width_mm,
        "height_mm": profile.height_mm,
        "printable_width_mm": profile.printable_width_mm,
        "printable_height_mm": profile.printable_height_mm,
        "safe_zone_mm": profile.safe_zone_mm,
        "item_count": profile.item_count,
        "layout_kind": profile.layout_kind,
        "layout_mode": profile.layout_mode,
        "is_generation_ready": profile.is_generation_ready,
        "validation_errors": profile.validation_errors,
    }
