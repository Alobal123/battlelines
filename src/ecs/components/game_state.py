"""Game state resource describing the active high-level mode."""
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class GameMode(Enum):
    """High-level game modes that drive which systems run."""
    MENU = auto()
    ABILITY_DRAFT = auto()
    SKILL_DRAFT = auto()
    LOCATION_DRAFT = auto()
    DIALOGUE = auto()
    COMBAT = auto()


@dataclass
class GameState:
    """Singleton component storing the currently active game mode."""
    mode: GameMode = GameMode.COMBAT
    input_guard_press_id: Optional[int] = None
