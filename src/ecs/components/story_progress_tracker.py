from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class StoryProgressTracker:
    """Aggregated progress that persists across game sessions."""

    enemies_defeated: int = 0
