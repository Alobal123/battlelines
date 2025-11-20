from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(slots=True)
class SkillListOwner:
    """Tracks skill entities owned by an entity."""

    skill_entities: List[int] = field(default_factory=list)
