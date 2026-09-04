"""Sous-classes d'articles spécialisées selon la catégorie métier."""

from dataclasses import dataclass
from typing import Dict, Any
from .articlesModel import BaseArticle


@dataclass
class WeightedArticle(BaseArticle):
    """Article vendu au poids / vrac (ex: Fruits, Fromage, Viande)."""

    tare_weight_g: float = 0.0  # Tare en grammes

    def price_per_kg(self) -> float:
        """Calcule le prix au kilo."""
        return self.pricing.effective_price

    def to_binding_context(self) -> Dict[str, Any]:
        ctx = super().to_binding_context()
        ctx.update({
            "PRIX_KILO": f"{self.price_per_kg():.2f} € / kg",
            "TARE": f"{self.tare_weight_g}g" if self.tare_weight_g > 0 else "",
            "IS_WEIGHTED": True,
        })
        return ctx


@dataclass
class BulkCaseArticle(BaseArticle):
    """Article vendu par carton / lot grossiste."""

    def unit_price_inside_case(self) -> float:
        """Calcule le prix unitaire d'un produit à l'intérieur du carton."""
        if self.packaging.case_size <= 0:
            return self.pricing.effective_price
        return self.pricing.effective_price / self.packaging.case_size

    def to_binding_context(self) -> Dict[str, Any]:
        ctx = super().to_binding_context()
        ctx.update({
            "UNIT_PRICE_IN_CASE": f"{self.unit_price_inside_case():.2f} € / unité",
            "CASE_LABEL": f"Carton de {int(self.packaging.case_size)} {self.packaging.pack_unit}",
            "IS_BULK": True,
        })
        return ctx