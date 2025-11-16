"""Components for the starting ability draft flow."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class StartingAbilityChoice:
    """Marks a choice window option as a starting ability pick."""

    owner_entity: int
    ability_name: str
