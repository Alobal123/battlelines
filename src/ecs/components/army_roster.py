from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class ArmyRoster:
    """Tracks regiment entities available to a player along with the active slot."""

    regiment_entities: List[int]
    active_index: int = 0

    def active_regiment(self) -> int:
        return self.regiment_entities[self.active_index]
