"""Components used by the main menu ECS subsystem."""
from dataclasses import dataclass
from enum import Enum, auto


class MenuAction(Enum):
    """Actions that a menu button can trigger."""
    NEW_GAME = auto()
    CONTINUE = auto()


@dataclass
class MenuButton:
    """Interactive button displayed in the main menu."""
    label: str
    action: MenuAction
    x: float
    y: float
    width: float = 240.0
    height: float = 64.0
    enabled: bool = True


@dataclass
class MenuBackground:
    """Background styling data for the menu screen."""
    color: tuple[int, int, int] = (20, 30, 50)


@dataclass
class MenuTag:
    """Marker component so menu entities can be cleaned up together."""
    pass
