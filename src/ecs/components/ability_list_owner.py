from dataclasses import dataclass
from typing import List

@dataclass(slots=True)
class AbilityListOwner:
    """Associates an entity with multiple ability entity ids."""
    ability_entities: List[int]