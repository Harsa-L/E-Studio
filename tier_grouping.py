"""Reconstruct price tiers from repeated article rows."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Any, Iterable
import re

from data_sources import ImportIssue, ImportedRow
from binding_profiles import BindingProfile
from data_normalization import normalize_row


@dataclass(frozen=True)
class TierGroupingConfig:
    article_key: str
    price_column: str | None = None
    quantity_column: str | None = None
    article_aliases: tuple[str, ...] = ()
    price_aliases: tuple[str, ...] = ("SELLING_PRICE", "PRICE", "UNIT_PRICE", "PROMO_PRICE")
    quantity_aliases: tuple[str, ...] = ("BUY_QTY", "PURCHASE_QTY", "QTY", "QUANTITY", "UP_TO")
    conflict_policy: str = "report"

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.article_key.strip():
            errors.append("An article grouping key is required.")
        if self.conflict_policy not in {"report", "lowest_price", "first"}:
            errors.append("Conflict policy must be report, lowest_price, or first.")
        return errors


@dataclass
class GroupedArticle:
    article_key: str
    rows: list[ImportedRow]
    base_price: float | None
    tiers: list[dict[str, Any]]
    issues: list[ImportIssue]

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


def _normalized(value: Any) -> str:
    text = str(value or "").strip().upper()
    return re.sub(r"[^A-Z0-9]+", "_", text).strip("_")


def _number(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("Boolean cannot be used as a quantity or price.")
    if isinstance(value, Real):
        return float(value)
    return float(str(value).strip().replace(" ", "").replace(",", "."))


def _quantity(value: Any) -> float:
    text = str(value or "").strip().lower()
    match = re.search(r"(?:up\s*to|jusqu\s*a|upto)\s*(\d+(?:[.,]\d+)?)", text)
    if match:
        return float(match.group(1).replace(",", "."))
    return _number(value)


def _find_column(row: ImportedRow, explicit: str | None, aliases: tuple[str, ...]) -> str | None:
    if explicit and explicit in row.raw_values:
        return explicit
    normalized_aliases = {_normalized(alias) for alias in aliases}
    for column in row.raw_values:
        if _normalized(column) in normalized_aliases:
            return column
    return None


def group_article_rows(rows: Iterable[ImportedRow], config: TierGroupingConfig) -> list[GroupedArticle]:
    """Group repeated rows and interpret quantity one as the base price."""
    if errors := config.validate():
        raise ValueError("Invalid tier grouping: " + "; ".join(errors))
    grouped: dict[str, list[ImportedRow]] = {}
    for row in rows:
        value = row.raw_values.get(config.article_key)
        if value is None or not str(value).strip():
            continue
        grouped.setdefault(str(value).strip(), []).append(row)

    results: list[GroupedArticle] = []
    for article_key, article_rows in grouped.items():
        issues: list[ImportIssue] = []
        tiers_by_qty: dict[float, list[float]] = {}
        for row in article_rows:
            quantity_column = _find_column(row, config.quantity_column, config.quantity_aliases)
            price_column = _find_column(row, config.price_column, config.price_aliases)
            if not quantity_column or not price_column:
                issues.append(ImportIssue("tier_column_missing", "Could not identify quantity and price columns.", "error", row.sheet, row.row_number))
                continue
            try:
                quantity = _quantity(row.raw_values.get(quantity_column))
                price = _number(row.raw_values.get(price_column))
                if quantity <= 0 or price < 0:
                    raise ValueError("Quantity must be positive and price cannot be negative.")
                tiers_by_qty.setdefault(quantity, []).append(price)
            except (TypeError, ValueError) as error:
                issues.append(ImportIssue("tier_value_invalid", str(error), "error", row.sheet, row.row_number, price_column))

        base_prices = tiers_by_qty.pop(1.0, [])
        base_price: float | None = None
        if base_prices:
            base_price = _resolve_conflict(base_prices, config, article_key, issues, "base price")
        tiers: list[dict[str, Any]] = []
        for quantity in sorted(tiers_by_qty):
            prices = tiers_by_qty[quantity]
            price = _resolve_conflict(prices, config, article_key, issues, f"quantity {quantity:g}")
            if price is not None:
                tiers.append({"qty": int(quantity) if quantity.is_integer() else quantity, "unit_price": price})
        if not base_prices and tiers:
            issues.append(ImportIssue("base_price_missing", "No quantity-1 row was found; base price is missing.", "error", article_rows[0].sheet, article_rows[0].row_number))
        results.append(GroupedArticle(article_key, article_rows, base_price, tiers, issues))
    return results


def normalize_grouped_articles(
    rows: Iterable[ImportedRow],
    profile: BindingProfile,
    config: TierGroupingConfig,
) -> list[tuple[dict[str, Any], list[ImportIssue], int]]:
    """Create one binding record per article group with reconstructed tiers."""
    grouped = group_article_rows(rows, config)
    normalized: list[tuple[dict[str, Any], list[ImportIssue], int]] = []
    for article in grouped:
        base = normalize_row(article.rows[0], profile)
        issues = [*base.issues, *article.issues]
        record = dict(base.record)
        if article.base_price is not None:
            record["SELLING_PRICE"] = article.base_price
        if article.tiers:
            record["TIERS"] = article.tiers
        normalized.append((record, issues, article.rows[0].row_number))
    return normalized


def _resolve_conflict(prices: list[float], config: TierGroupingConfig, article_key: str, issues: list[ImportIssue], label: str) -> float | None:
    unique = sorted(set(prices))
    if len(unique) == 1:
        return unique[0]
    if config.conflict_policy == "lowest_price":
        issues.append(ImportIssue("tier_price_conflict", f"Conflicting {label} values for {article_key}; lowest price selected.", "warning"))
        return unique[0]
    if config.conflict_policy == "first":
        issues.append(ImportIssue("tier_price_conflict", f"Conflicting {label} values for {article_key}; first price selected.", "warning"))
        return prices[0]
    issues.append(ImportIssue("tier_price_conflict", f"Conflicting {label} values for {article_key}.", "error"))
    return None
