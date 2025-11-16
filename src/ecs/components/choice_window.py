"""Components describing the generic choice window UI."""
from dataclasses import dataclass, field
from typing import Optional, Tuple, List


@dataclass(slots=True)
class ChoiceWindow:
    """Container for a set of selectable options rendered in panels."""

    option_entities: List[int] = field(default_factory=list)
    skippable: bool = False
    title: Optional[str] = None
    panel_gap: float = 24.0
    overlay_color: Tuple[int, int, int, int] = (0, 0, 0, 190)
    skip_button_bounds: Optional[Tuple[float, float, float, float]] = None


@dataclass(slots=True)
class ChoiceOption:
    """Individual choice entry displayed within the choice window."""

    window_entity: int
    label: str
    description: str = ""
    payload_entity: Optional[int] = None
    width: float = 240.0
    height: float = 160.0
    order: int = 0
    bounds: Optional[Tuple[float, float, float, float]] = None


@dataclass(slots=True)
class ChoiceTag:
    """Marker used to group all entities participating in a choice window."""

    pass
