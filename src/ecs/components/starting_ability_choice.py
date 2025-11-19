"""Components for the starting ability draft flow."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AbilityChoice:
    """Marks a choice window option as an ability pick."""

    owner_entity: int
    ability_name: str
