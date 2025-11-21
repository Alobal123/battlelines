from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(slots=True)
class LocationChoice:
    """Choice metadata for selecting a location."""

    owner_entity: int
    location_slug: str


@dataclass(slots=True)
class CurrentLocation:
    """Tracks the currently selected location for an entity."""

    slug: str
    name: str
    description: str
    enemy_names: Tuple[str, ...]
