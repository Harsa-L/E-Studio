"""Resolve price tiers from an article binding context."""

from __future__ import annotations

from dataclasses import dataclass, field
from numbers import Real
from typing import List, Dict, Any


class CancelLabelGenerationException(Exception):
    """Exception levée lorsqu'un paramètre requis est introuvable, annulant l'étiquette."""
    pass


@dataclass
class TierTargetSpec:
    """Configuration de ciblage d'un palier pour un objet du gabarit."""
    
    primary_index: int
    fallback_indices: List[int] = field(default_factory=list)
    fallback_to_base_price: bool = True
    strict_required: bool = False
    keyword_prefix: str = "À partir de"
    unit_label: str = "Pcs"


class TierResolver:
    """Évalue et extrait le prix approprié selon les données réelles de l'article."""

    @staticmethod
    def resolve(spec: TierTargetSpec, article_data: Dict[str, Any]) -> Dict[str, Any]:
        tiers = article_data.get("TIERS", [])
        if not isinstance(tiers, list):
            tiers = []
        search_chain = [spec.primary_index] + spec.fallback_indices

        # 1. Recherche par ordre de priorité dans la chaîne
        for index in search_chain:
            if 0 <= index < len(tiers):
                selected = tiers[index]
                if not isinstance(selected, dict) or "qty" not in selected:
                    continue
                unit_price = selected.get("unit_price")
                if isinstance(unit_price, bool) or not isinstance(unit_price, Real):
                    continue
                unit_price = float(unit_price)
                return {
                    "text_qty": f"{spec.keyword_prefix} {selected['qty']} {selected.get('unit', spec.unit_label)}",
                    "unit_price": unit_price,
                    "formatted_price": f"{unit_price:.0f} {article_data.get('CURRENCY', 'FCFA')}",
                    "is_fallback": index != spec.primary_index
                }

        # 2. Repli sur le prix standard
        base_price = article_data.get("SELLING_PRICE")
        if spec.fallback_to_base_price and isinstance(base_price, Real) and not isinstance(base_price, bool):
            base_price = float(base_price)
            return {
                "text_qty": f"{spec.keyword_prefix} 1 {spec.unit_label}",
                "unit_price": base_price,
                "formatted_price": f"{base_price:.0f} {article_data.get('CURRENCY', 'FCFA')}",
                "is_fallback": True
            }

        # 3. Annulation si paramètre requis non disponible
        if spec.strict_required:
            raise CancelLabelGenerationException(
                f"Annulation : Palier {spec.primary_index + 1} introuvable et strict_required=True."
            )

        return {}