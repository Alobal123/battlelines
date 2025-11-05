from dataclasses import dataclass, field
from typing import Dict

@dataclass(slots=True)
class TileBank:
    """Stores accumulated tiles (by tile type name) for an owner entity.

    owner_entity: the entity (e.g., player) whose clears contribute.
    counts: mapping of tile type name -> number of tiles available for spending.
    """
    owner_entity: int
    counts: Dict[str, int] = field(default_factory=dict)

    def add(self, type_name: str, amount: int = 1):
        if amount <= 0:
            return
        self.counts[type_name] = self.counts.get(type_name, 0) + amount

    def can_spend(self, cost: Dict[str, int]) -> bool:
        return all(self.counts.get(t, 0) >= n for t, n in cost.items())

    def spend(self, cost: Dict[str, int]) -> Dict[str, int]:
        """Attempt to spend cost; returns missing dict if insufficient else empty dict."""
        missing = {t: n - self.counts.get(t, 0) for t, n in cost.items() if self.counts.get(t, 0) < n}
        if missing:
            return missing
        for t, n in cost.items():
            self.counts[t] -= n
        return {}
