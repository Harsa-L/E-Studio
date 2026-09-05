"""Typed sales-article models and their label binding context."""

from __future__ import annotations
from dataclasses import dataclass, field
from abc import ABC
from typing import Any, Dict, Optional, TypeAlias


BindingContext: TypeAlias = Dict[str, Any]


@dataclass(frozen=True)
class ProductIdent:
    part_no: str
    product_scan: str  # Code EAN-13 / Code-barres
    item_name: str
    description: str = ""
    brand_info: str = ""


@dataclass(frozen=True)
class HierarchyInfo:
    div_name: str = ""
    dept_name: str = ""
    category_name: str = ""
    sub_category_name: str = ""


@dataclass(frozen=True)
class PackagingInfo:
    pack_unit: str = "PCE"        # Ex: "100g", "1L", "PCE"
    selling_unit: str = "PCE"     # Ex: "KG", "PCE"
    case_size: float = 1.0        # Nb d'unités par carton
    case_unit: str = "CT"         # Ex: "CT", "PAC"


@dataclass(frozen=True)
class TaxInfo:
    tax: str = "TVA"             # Ex: "TVA 20%"
    tax_rate: float = 20.0       # En pourcentage (20.0 = 20%)
    tax_type: str = "INCLUDED"   # "INCLUDED" (TTC) ou "EXCLUDED" (HT)

    def calculate_vat_amount(self, price_ttc: float) -> float:
        """Calcule le montant exact de la taxe à partir du prix TTC."""
        return price_ttc - (price_ttc / (1.0 + (self.tax_rate / 100.0)))


@dataclass
class PricingInfo:
    selling_price: float
    promo_price: Optional[float] = None
    item_type: str = "STANDARD"  # "STANDARD", "PROMO", "CLEARANCE"

    @property
    def has_promo(self) -> bool:
        return self.promo_price is not None and self.promo_price < self.selling_price

    @property
    def effective_price(self) -> float:
        """Retourne le prix à payer réellement par le client."""
        return self.promo_price if self.has_promo else self.selling_price

    @property
    def discount_percentage(self) -> float:
        """Calcule automatiquement le pourcentage de remise."""
        if not self.has_promo or self.selling_price <= 0:
            return 0.0
        return round((1.0 - (self.promo_price / self.selling_price)) * 100, 0)

    @property
    def discount_amount(self) -> float:
        """Calcule l'économie réalisée par le client."""
        if not self.has_promo:
            return 0.0
        return self.selling_price - self.promo_price


@dataclass
class BaseArticle(ABC):
    """Classe de base représentant un article en vente.
    
    Fournit l'interface commune et la conversion automatique vers le Dictionnaire de Data Binding.
    """
    ident: ProductIdent
    pricing: PricingInfo
    store_name: str = ""
    vendor_name: str = ""
    currency: str = "€"
    tiers: list[Dict[str, Any]] = field(default_factory=list)
    hierarchy: HierarchyInfo = field(default_factory=HierarchyInfo)
    packaging: PackagingInfo = field(default_factory=PackagingInfo)
    tax: TaxInfo = field(default_factory=TaxInfo)

    def to_binding_context(self) -> BindingContext:
        """Convertit l'article en dictionnaire plat enrichi pour le moteur de templates/étiquettes.
        
        Permet de lier directement des clés comme 'PRIX_TTC', 'TAUX_PROMO' ou 'PRIX_KILO' dans le canvas UI.
        """
        p = self.pricing
        t = self.tax
        pkg = self.packaging

        vat_amount = t.calculate_vat_amount(p.effective_price)
        price_ht = p.effective_price - vat_amount

        return {
            # Identification & Vendeur
            "STORE_NAME": self.store_name,
            "VENDOR_NAME": self.vendor_name,
            "PARTNO": self.ident.part_no,
            "PRODUCT_SCAN": self.ident.product_scan,
            "ITEMNAME": self.ident.item_name,
            "ITEMDESCRIPTION": self.ident.description,
            "BRAND_INFO": self.ident.brand_info,

            # Hiérarchie commerciale
            "DIV_NAME": self.hierarchy.div_name,
            "DEPT_NAME": self.hierarchy.dept_name,
            "CATEGORY_NAME": self.hierarchy.category_name,
            "SUB_CATEGORY_NAME": self.hierarchy.sub_category_name,

            # Conditionnement
            "PACK_UNIT": pkg.pack_unit,
            "SELLING_UNIT": pkg.selling_unit,
            "CASE_SIZE": str(pkg.case_size),
            "CASE_UNIT": pkg.case_unit,

            # Prix & Tarification. Numeric keys are consumed by TierResolver;
            # display-specific keys keep formatting out of the business layer.
            "CURRENCY": self.currency,
            "TIERS": list(self.tiers),
            "SELLING_PRICE": p.selling_price,
            "SELLING_PRICE_DISPLAY": f"{p.selling_price:.2f} {self.currency}",
            "PROMOPRICE": p.promo_price,
            "PROMOPRICE_DISPLAY": f"{p.promo_price:.2f} {self.currency}" if p.promo_price is not None else "",
            "EFFECTIVE_PRICE": p.effective_price,
            "EFFECTIVE_PRICE_DISPLAY": f"{p.effective_price:.2f} {self.currency}",
            "HAS_PROMO": p.has_promo,
            "DISCOUNT_PCT": f"-{int(p.discount_percentage)}%" if p.has_promo else "",
            "DISCOUNT_AMOUNT": p.discount_amount if p.has_promo else 0.0,
            "DISCOUNT_AMOUNT_DISPLAY": f"-{p.discount_amount:.2f} {self.currency}" if p.has_promo else "",
            "ITEM_TYPE": p.item_type,

            # Taxes & Prix HT
            "PRICE_HT": price_ht,
            "PRICE_HT_DISPLAY": f"{price_ht:.2f} {self.currency}",
            "TAX_AMOUNT": vat_amount,
            "TAX_AMOUNT_DISPLAY": f"{vat_amount:.2f} {self.currency}",
            "TAX": t.tax,
            "TAX_RATE": f"{t.tax_rate:.1f}%",
            "TAX_TYPE": t.tax_type,
        }