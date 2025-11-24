from dataclasses import dataclass, field
from typing import Tuple


@dataclass(slots=True)
class ForbiddenKnowledge:
    """Tracks global forbidden knowledge progress accrued from Secrets matches."""

    value: int = 0
    max_value: int = 100
    chaos_released: bool = False
    baseline_spawnable: Tuple[str, ...] = field(default_factory=tuple)
