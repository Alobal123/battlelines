from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass(slots=True)
class Skill:
    """Describes a passive skill owned by an entity."""

    name: str
    description: str
    tags: Tuple[str, ...] = field(default_factory=tuple)
    affinity_bonus: Dict[str, int] = field(default_factory=dict)
