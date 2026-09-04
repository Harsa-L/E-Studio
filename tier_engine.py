"""Moteur de résolution des paliers de prix avec fallback et annulation."""

from dataclasses import dataclass, field
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
        search_chain = [spec.primary_index] + spec.fallback_indices

        # 1. Recherche par ordre de priorité dans la chaîne
        for index in search_chain:
            if 0 <= index < len(tiers):
                selected = tiers[index]
                return {
                    "text_qty": f"{spec.keyword_prefix} {selected['qty']} {selected.get('unit', spec.unit_label)}",
                    "unit_price": selected["unit_price"],
                    "formatted_price": f"{selected['unit_price']:.0f} {article_data.get('CURRENCY', 'FCFA')}",
                    "is_fallback": index != spec.primary_index
                }

        # 2. Repli sur le prix standard
        if spec.fallback_to_base_price and "SELLING_PRICE" in article_data:
            base_price = article_data["SELLING_PRICE"]
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