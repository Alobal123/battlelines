from dataclasses import dataclass

@dataclass
class Board:
    rows: int
    cols: int
    # Future: palette, level id, combo state, etc.
