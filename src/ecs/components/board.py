from dataclasses import dataclass

@dataclass(slots=True)
class Board:
    rows: int
    cols: int
    # Future: palette, level id, combo state, etc.
