"""Convert imported spreadsheet rows into typed label binding contexts."""

from __future__ import annotations

from datetime import date, datetime
from math import isnan
from numbers import Real
from typing import Any
import re

from core.workflows.binding_profiles import BindingProfile, ColumnMapping
from core.workflows.data_sources import ImportedRow, ImportIssue


class RowNormalizationResult:
    def __init__(self, record: dict[str, Any], display_values: dict[str, str], issues: list[ImportIssue]):
        self.record = record
        self.display_values = display_values
        self.issues = issues

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


def _missing(value: Any) -> bool:
    return value is None or (isinstance(value, float) and isnan(value)) or (isinstance(value, str) and not value.strip())


def _number(value: Any) -> float | int:
    if isinstance(value, bool):
        raise ValueError("Boolean is not a number.")
    if isinstance(value, Real):
        return value
    text = str(value).strip().replace(" ", "").replace(",", ".")
    number = float(text)
    return int(number) if number.is_integer() else number


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "oui", "o"}:
        return True
    if text in {"0", "false", "no", "n", "non"}:
        return False
    raise ValueError(f"Unrecognized boolean value: {value!r}")


def _date(value: Any, date_format: str) -> str:
    if isinstance(value, (datetime, date)):
        return value.strftime(date_format)
    parsed = datetime.fromisoformat(str(value).strip())
    return parsed.strftime(date_format)


def _convert(value: Any, mapping: ColumnMapping) -> Any:
    if _missing(value):
        return mapping.default
    if mapping.field_type in {"number", "currency"}:
        return _number(value)
    if mapping.field_type == "boolean":
        return _boolean(value)
    if mapping.field_type == "date":
        return _date(value, mapping.date_format)
    return str(value) if mapping.field_type in {"text", "image", "barcode", "qrcode"} else value


def _build_tiers(values: dict[str, Any], raw_values: dict[str, Any], prefix: str, row: ImportedRow) -> tuple[list[dict[str, Any]], list[ImportIssue]]:
    groups: dict[int, dict[str, Any]] = {}
    issues: list[ImportIssue] = []
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)_(QTY|PRICE|UNIT)$", re.IGNORECASE)
    for column, value in raw_values.items():
        match = pattern.match(column.strip())
        if not match:
            continue
        index, part = int(match.group(1)), match.group(2).lower()
        groups.setdefault(index, {})[part] = value
    tiers: list[dict[str, Any]] = []
    for index in sorted(groups):
        group = groups[index]
        if _missing(group.get("qty")) and _missing(group.get("price")):
            continue
        try:
            if _missing(group.get("qty")) or _missing(group.get("price")):
                raise ValueError("Tier quantity and price are both required.")
            qty = _number(group["qty"])
            price = _number(group["price"])
            if qty <= 0 or price < 0:
                raise ValueError("Tier quantity must be positive and price cannot be negative.")
            tier = {"qty": qty, "unit_price": price}
            if not _missing(group.get("unit")):
                tier["unit"] = str(group["unit"])
            tiers.append(tier)
        except (TypeError, ValueError) as error:
            issues.append(ImportIssue("invalid_tier", str(error), "error", row.sheet, row.row_number))
    return tiers, issues


def normalize_row(row: ImportedRow, profile: BindingProfile) -> RowNormalizationResult:
    record: dict[str, Any] = {}
    display_values: dict[str, str] = {}
    issues: list[ImportIssue] = []
    for mapping in profile.mappings:
        raw = row.raw_values.get(mapping.source_column)
        try:
            value = _convert(raw, mapping)
            if mapping.required and _missing(value):
                raise ValueError("Required value is missing.")
            record[mapping.target_key] = value
            display_values[mapping.target_key] = "" if value is None else str(value)
        except (TypeError, ValueError) as error:
            issues.append(ImportIssue("conversion_error", str(error), "error", row.sheet, row.row_number, mapping.source_column))
    tiers, tier_issues = _build_tiers(record, row.raw_values, profile.tier_prefix, row)
    if tiers:
        record["TIERS"] = tiers
    issues.extend(tier_issues)
    return RowNormalizationResult(record, display_values, issues)
