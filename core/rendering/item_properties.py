"""Descripteurs de propriétés génériques pour l'inspection dynamique."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Any, List, Optional

MULTIPLE_VALUES_INDICATOR = "---"


@dataclass
class PropertySpec:
    """Spécification d'une propriété modifiable exposée par un objet du canvas."""
    
    key: str
    label: str
    type_name: str  # "float", "int", "str", "bool"
    category: str
    getter: Callable[[], Any]
    setter: Callable[[Any], None]
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    suffix: str = ""