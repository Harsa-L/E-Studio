"""Serializable mappings between source columns and label binding keys."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import json

from domain_fields import DOMAIN_FIELDS, canonical_domain_key


SUPPORTED_FIELD_TYPES = {"text", "number", "currency", "boolean", "date", "image", "barcode", "qrcode"}


def suggest_mappings(headers: list[str]) -> dict[str, str]:
    """Suggest canonical binding keys and field types from source headers."""
    suggestions: dict[str, str] = {}
    fields_by_key = {field.key.value: field for field in DOMAIN_FIELDS}
    for header in headers:
        key = canonical_domain_key(header)
        if key is None:
            normalized = header.strip().upper().replace(" ", "_")
            suggestions[header] = header
            suggestions[f"{header}:type"] = "text"
            continue
        field = fields_by_key[key]
        suggestions[header] = key
        suggestions[f"{header}:type"] = field.value_type
    return suggestions


@dataclass(frozen=True)
class ColumnMapping:
    source_column: str
    target_key: str
    field_type: str = "text"
    required: bool = False
    default: Any = None
    date_format: str = "%Y-%m-%d"

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.source_column.strip():
            errors.append("Source column cannot be empty.")
        if not self.target_key.strip():
            errors.append("Target binding key cannot be empty.")
        if self.field_type not in SUPPORTED_FIELD_TYPES:
            errors.append(f"Unsupported field type: {self.field_type}")
        return errors


@dataclass
class BindingProfile:
    name: str = "Default"
    mappings: list[ColumnMapping] = field(default_factory=list)
    tier_prefix: str = "TIER_"

    def validate(self, source_columns: set[str] | None = None) -> list[str]:
        errors: list[str] = []
        target_keys: set[str] = set()
        for mapping in self.mappings:
            errors.extend(mapping.validate())
            if mapping.target_key in target_keys:
                errors.append(f"Duplicate target binding key: {mapping.target_key}")
            target_keys.add(mapping.target_key)
            if source_columns is not None and mapping.source_column not in source_columns:
                errors.append(f"Missing source column: {mapping.source_column}")
        return errors

    def to_json(self) -> str:
        if errors := self.validate():
            raise ValueError("Invalid binding profile: " + "; ".join(errors))
        return json.dumps({"name": self.name, "tier_prefix": self.tier_prefix, "mappings": [asdict(item) for item in self.mappings]}, indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, value: str) -> "BindingProfile":
        data = json.loads(value)
        if not isinstance(data, dict) or not isinstance(data.get("mappings", []), list):
            raise ValueError("Binding profile JSON must contain a mappings array.")
        mappings = [ColumnMapping(**item) for item in data["mappings"]]
        profile = cls(str(data.get("name", "Default")), mappings, str(data.get("tier_prefix", "TIER_")))
        if errors := profile.validate():
            raise ValueError("Invalid binding profile: " + "; ".join(errors))
        return profile
