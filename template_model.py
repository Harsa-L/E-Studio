"""Modèle de données du Gabarit (Holder) sans paramètres prédéfinis."""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any
import json


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
    items: List[Dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> str:
        """Export du gabarit au format JSON."""
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> LabelTemplate:
        """Chargement du gabarit depuis une chaîne JSON."""
        data = json.loads(json_str)
        data["inner_margins_mm"] = Margins(**data["inner_margins_mm"])
        data["outer_margins_mm"] = Margins(**data["outer_margins_mm"])
        return cls(**data)