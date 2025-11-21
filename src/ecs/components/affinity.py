from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class Affinity:
    """Tracks elemental affinities and their contributing sources for an entity.

    Attributes:
        base: Static alignment values defined by the character or loadout.
        totals: Aggregated affinities including base, abilities, and skills.
        contributions: Grouped contribution totals keyed by source category
            ("base", "abilities", "skills", etc.).
        breakdown: Ordered list of contribution records. Each record is a
            dictionary with keys ``source`` (category label), ``label``
            (human-readable name), and ``values`` (tile -> amount mapping).
    """

    base: Dict[str, int] = field(default_factory=dict)
    totals: Dict[str, int] = field(default_factory=dict)
    contributions: Dict[str, Dict[str, int]] = field(default_factory=dict)
    breakdown: List[Dict[str, object]] = field(default_factory=list)

    def reset_dynamic(self) -> None:
        """Clear computed fields while keeping the base alignment."""
        self.totals.clear()
        self.contributions.clear()
        self.breakdown.clear()
