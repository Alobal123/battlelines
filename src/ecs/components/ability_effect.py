from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AbilityEffectTarget = Literal[
    "self",
    "opponent",
    "pending_target",
    "pending_target_or_self",
    "board",
]


@dataclass(slots=True)
class AbilityEffectSpec:
    """Describes an effect emitted when an ability resolves."""

    slug: str
    target: AbilityEffectTarget
    turns: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    param_overrides: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class AbilityEffects:
    """Collection of effect specs attached to an ability entity."""

    effects: tuple[AbilityEffectSpec, ...] = ()
