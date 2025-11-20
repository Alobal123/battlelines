from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Tuple


@dataclass(slots=True)
class SkillEffectSpec:
    """Effect payload that should be applied when the skill is granted."""

    slug: str
    turns: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SkillEffects:
    """Collection of effect specs attached to a skill entity."""

    effects: Tuple[SkillEffectSpec, ...] = ()
