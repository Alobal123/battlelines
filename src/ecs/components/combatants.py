from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Combatants:
    """Stores the canonical player and opponent entities for the current combat."""

    player_entity: int
    opponent_entity: int
