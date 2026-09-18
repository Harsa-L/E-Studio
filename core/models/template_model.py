"""Typed, versioned document model for printable label templates."""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, TypeAlias
import json
import math


SCHEMA_VERSION = 1
TemplateItemData: TypeAlias = Dict[str, Any]
BACKGROUND_FIT_MODES = {"contain", "cover", "stretch"}


@dataclass
class Margins:
    top: float
    bottom: float
    left: float
    right: float


@dataclass
class LabelTemplate:
    """Gabarit d'étiquette dont les paramètres doivent être définis à la création."""

    name: str
    width_mm: float
    height_mm: float
    inner_margins_mm: Margins
    outer_margins_mm: Margins
    layout_kind: str = "fixed"
    layout_mode: str = "single"
    bg_color: str = "#FFFFFF"
    bg_opacity: float = 1.0
    background_image_path: str | None = None
    background_image_opacity: float = 0.35
    background_image_fit: str = "contain"
    background_image_visible: bool = True
    background_image_locked: bool = True
    background_image_in_output: bool = False
    items: List[TemplateItemData] = field(default_factory=list)

    def validate(self) -> List[str]:
        errors = []
        if not self.name.strip():
            errors.append("Template name cannot be empty.")
        numeric_values = [
            self.width_mm,
            self.height_mm,
            self.bg_opacity,
            self.background_image_opacity,
        ]
        numeric_values.extend(
            value
            for margins in (self.inner_margins_mm, self.outer_margins_mm)
            for value in (margins.top, margins.bottom, margins.left, margins.right)
        )
        numeric_values_valid = all(
            isinstance(value, (int, float)) and math.isfinite(value)
            for value in numeric_values
        )
        if not numeric_values_valid:
            errors.append("Template dimensions, margins, and opacity must be finite numbers.")
        if numeric_values_valid and (self.width_mm <= 0 or self.height_mm <= 0):
            errors.append("Template dimensions must be greater than zero.")
        if numeric_values_valid:
            for label, margins in (("inner", self.inner_margins_mm), ("outer", self.outer_margins_mm)):
                if min(margins.top, margins.bottom, margins.left, margins.right) < 0:
                    errors.append(f"{label.title()} margins cannot be negative.")
            printable_width = self.width_mm - self.inner_margins_mm.left - self.inner_margins_mm.right
            printable_height = self.height_mm - self.inner_margins_mm.top - self.inner_margins_mm.bottom
            if printable_width <= 0 or printable_height <= 0:
                errors.append("Inner margins must leave a printable area.")
        if not isinstance(self.layout_kind, str) or not self.layout_kind.strip():
            errors.append("Layout kind must be a non-empty string.")
        if not isinstance(self.layout_mode, str) or not self.layout_mode.strip():
            errors.append("Layout mode must be a non-empty string.")
        if numeric_values_valid and not 0 <= self.bg_opacity <= 1:
            errors.append("Background opacity must be between 0 and 1.")
        if numeric_values_valid and not 0 <= self.background_image_opacity <= 1:
            errors.append("Background image opacity must be between 0 and 1.")
        if self.background_image_fit not in BACKGROUND_FIT_MODES:
            errors.append(f"Unsupported background image fit mode: {self.background_image_fit}")
        if self.background_image_in_output:
            errors.append("Background reference images cannot be included in output.")
        item_ids = [item.get("id") for item in self.items if isinstance(item, dict)]
        if len(item_ids) != len(set(item_ids)):
            errors.append("Template item identifiers must be unique.")
        return errors

    def to_json(self) -> str:
        """Export du gabarit au format JSON."""
        if errors := self.validate():
            raise ValueError("Invalid template: " + "; ".join(errors))
        data = asdict(self)
        data["schema_version"] = SCHEMA_VERSION
        return json.dumps(data, indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> LabelTemplate:
        """Chargement du gabarit depuis une chaîne JSON."""
        data = json.loads(json_str)
        if not isinstance(data, dict):
            raise ValueError("Template JSON must contain an object.")
        data = dict(data)
        version = data.pop("schema_version", 1)
        if version != SCHEMA_VERSION:
            raise ValueError(f"Unsupported template schema version: {version}")
        try:
            data["inner_margins_mm"] = Margins(**data["inner_margins_mm"])
            data["outer_margins_mm"] = Margins(**data["outer_margins_mm"])
        except (KeyError, TypeError) as error:
            raise ValueError("Template margins must contain top, bottom, left, and right.") from error
        template = cls(**data)
        if errors := template.validate():
            raise ValueError("Invalid template: " + "; ".join(errors))
        return template