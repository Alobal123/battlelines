from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class TurnState:
    """Tracks current turn-level state shared across systems."""

    action_source: Optional[str] = None
    cascade_active: bool = False
    cascade_depth: int = 0
    cascade_observed: bool = False
    ability_entity: Optional[int] = None
    ability_ends_turn: bool = True
