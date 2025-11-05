from dataclasses import dataclass

@dataclass(slots=True)
class BoardPosition:
    row: int
    col: int
