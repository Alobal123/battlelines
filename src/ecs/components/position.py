from dataclasses import dataclass

@dataclass(slots=True)
class Position:
    x: float
    y: float
