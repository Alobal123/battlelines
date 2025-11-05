from dataclasses import dataclass

@dataclass(slots=True)
class AbilityOwner:
    """Associates an entity with an ability entity it owns/controls."""
    ability_entity: int
