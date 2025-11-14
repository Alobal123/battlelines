from dataclasses import dataclass
from typing import Tuple


@dataclass(slots=True)
class TooltipState:
    """Single tooltip state shared across the UI layer."""

    visible: bool = False
    lines: Tuple[str, ...] = ()
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    padding: float = 6.0
    line_height: float = 16.0
    target: str = ""
    target_id: int | None = None
