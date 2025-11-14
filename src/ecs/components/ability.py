from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass(slots=True)
class Ability:
    """Represents a player-usable ability.

    Fields:
      name: Display / reference name.
      kind: Semantic category (e.g., 'active', 'passive', 'special').
      cost: Mapping of tile type names to counts consumed when activated.
      description: Text description of the ability effect (for UI display).
      params: Arbitrary configuration values 
      cooldown: Number of player turns required before re-use.
    """
    name: str
    kind: str
    cost: Dict[str, int]
    description: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    cooldown: int = 0
