"""Typed, versioned document model for printable label templates."""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, TypeAlias
import json


SCHEMA_VERSION = 1
TemplateItemData: TypeAlias = Dict[str, Any]


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
    bg_color: str = "#FFFFFF"
    bg_opacity: float = 1.0
    items: List[TemplateItemData] = field(default_factory=list)

    def validate(self) -> List[str]:
        errors = []
        if not self.name.strip():
            errors.append("Template name cannot be empty.")
        if self.width_mm <= 0 or self.height_mm <= 0:
            errors.append("Template dimensions must be greater than zero.")
        for label, margins in (("inner", self.inner_margins_mm), ("outer", self.outer_margins_mm)):
            if min(margins.top, margins.bottom, margins.left, margins.right) < 0:
                errors.append(f"{label.title()} margins cannot be negative.")
        printable_width = self.width_mm - self.inner_margins_mm.left - self.inner_margins_mm.right
        printable_height = self.height_mm - self.inner_margins_mm.top - self.inner_margins_mm.bottom
        if printable_width <= 0 or printable_height <= 0:
            errors.append("Inner margins must leave a printable area.")
        if not 0 <= self.bg_opacity <= 1:
            errors.append("Background opacity must be between 0 and 1.")
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
        version = data.pop("schema_version", 1)
        if version != SCHEMA_VERSION:
            raise ValueError(f"Unsupported template schema version: {version}")
        data["inner_margins_mm"] = Margins(**data["inner_margins_mm"])
        data["outer_margins_mm"] = Margins(**data["outer_margins_mm"])
        template = cls(**data)
        if errors := template.validate():
            raise ValueError("Invalid template: " + "; ".join(errors))
        return template