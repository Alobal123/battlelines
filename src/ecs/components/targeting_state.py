from dataclasses import dataclass

@dataclass(slots=True)
class TargetingState:
    """Marks that the player is in ability targeting mode.

    Fields:
      ability_entity: the ability being targeted.
    """
    ability_entity: int
