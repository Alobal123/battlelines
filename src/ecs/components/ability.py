from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass(slots=True)
class Ability:
    """Represents a player-usable ability.

    Fields:
      name: Display / reference name.
      kind: Semantic category (e.g., 'active', 'passive', 'special').
      cost: Mapping of tile type names to counts consumed when activated.
      params: Arbitrary configuration values 
    """
    name: str
    kind: str
    cost: Dict[str, int]
    params: Dict[str, Any] = field(default_factory=dict)
