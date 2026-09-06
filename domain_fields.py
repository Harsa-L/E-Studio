"""Canonical domain binding fields for specialized label objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DomainFieldKey(str, Enum):
    STORE_NAME = "STORE_NAME"
    PRODUCT_SCAN = "PRODUCT_SCAN"
    PARTNO = "PARTNO"
    ITEMNAME = "ITEMNAME"
    ITEMDESCRIPTION = "ITEMDESCRIPTION"
    DIV_NAME = "DIV_NAME"
    DEPT_NAME = "DEPT_NAME"
    CATEGORY_NAME = "CATEGORY_NAME"
    SUB_CATEGORY_NAME = "SUB_CATEGORY_NAME"
    BRAND_INFO = "BRAND_INFO"
    PACK_UNIT = "PACK_UNIT"
    VENDOR_NAME = "VENDOR_NAME"
    SELLING_UNIT = "SELLING_UNIT"
    SELLING_PRICE = "SELLING_PRICE"
    PROMOPRICE = "PROMOPRICE"
    ITEM_TYPE = "ITEM_TYPE"
    CASE_SIZE = "CASE_SIZE"
    CASE_UNIT = "CASE_UNIT"
    TAX = "TAX"
    TAX_RATE = "TAX_RATE"
    TAX_TYPE = "TAX_TYPE"


@dataclass(frozen=True)
class DomainField:
    key: DomainFieldKey
    label: str
    value_type: str
    aliases: tuple[str, ...] = ()
    numeric: bool = False


DOMAIN_FIELDS: tuple[DomainField, ...] = (
    DomainField(DomainFieldKey.STORE_NAME, "Nom du magasin", "text", ("STORE",)),
    DomainField(DomainFieldKey.PRODUCT_SCAN, "Code-barres produit", "barcode", ("EAN", "GTIN")),
    DomainField(DomainFieldKey.PARTNO, "Référence", "text", ("SKU", "PART NUMBER")),
    DomainField(DomainFieldKey.ITEMNAME, "Nom article", "text", ("PRODUCT NAME", "NAME")),
    DomainField(DomainFieldKey.ITEMDESCRIPTION, "Description", "text"),
    DomainField(DomainFieldKey.DIV_NAME, "Division", "text", ("DIV.NAME", "DIVISION")),
    DomainField(DomainFieldKey.DEPT_NAME, "Département", "text", ("DEPARTMENT",)),
    DomainField(DomainFieldKey.CATEGORY_NAME, "Catégorie", "text", ("CATEGORY",)),
    DomainField(DomainFieldKey.SUB_CATEGORY_NAME, "Sous-catégorie", "text", ("SUBCATEGORY",)),
    DomainField(DomainFieldKey.BRAND_INFO, "Marque", "text", ("BRAND",)),
    DomainField(DomainFieldKey.PACK_UNIT, "Unité de conditionnement", "text"),
    DomainField(DomainFieldKey.VENDOR_NAME, "Fournisseur", "text", ("VENDOR",)),
    DomainField(DomainFieldKey.SELLING_UNIT, "Unité de vente", "text"),
    DomainField(DomainFieldKey.SELLING_PRICE, "Prix de vente", "currency", ("PRICE",), True),
    DomainField(DomainFieldKey.PROMOPRICE, "Prix promotionnel", "currency", ("PROMO PRICE",), True),
    DomainField(DomainFieldKey.ITEM_TYPE, "Type article", "text"),
    DomainField(DomainFieldKey.CASE_SIZE, "Taille carton", "number", ("CASE QTY",), True),
    DomainField(DomainFieldKey.CASE_UNIT, "Unité carton", "text"),
    DomainField(DomainFieldKey.TAX, "Taxe", "text"),
    DomainField(DomainFieldKey.TAX_RATE, "Taux de taxe", "number", ("VAT RATE",), True),
    DomainField(DomainFieldKey.TAX_TYPE, "Type de taxe", "text"),
)

DOMAIN_FIELD_BY_KEY = {field.key.value: field for field in DOMAIN_FIELDS}
DOMAIN_FIELD_ALIASES = {
    alias.upper().replace(" ", "_"): field.key.value
    for field in DOMAIN_FIELDS
    for alias in field.aliases
}


def canonical_domain_key(value: str) -> str | None:
    normalized = "_".join(value.strip().upper().replace(".", "_").replace("-", "_").split())
    if normalized in DOMAIN_FIELD_BY_KEY:
        return normalized
    return DOMAIN_FIELD_ALIASES.get(normalized)
