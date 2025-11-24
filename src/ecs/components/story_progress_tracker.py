from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set, List


@dataclass(slots=True)
class StoryProgressTracker:
    """Aggregated progress that persists across game sessions."""

    enemies_defeated: int = 0
    
    # Story events tracking
    locations_visited: Set[str] = field(default_factory=set)
    enemies_encountered: Set[str] = field(default_factory=set)
    dialogues_completed: Set[str] = field(default_factory=set)
    
    # Progression tracking
    abilities_unlocked: List[str] = field(default_factory=list)
    skills_gained: Set[str] = field(default_factory=set)
    
    # Current location progress (not persisted, resets per location)
    current_location_slug: str | None = None
    current_location_enemies_defeated: int = 0
    locations_completed: int = 0
