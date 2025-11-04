from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass
class TileColor:
    # Use Optional so None can represent an empty cell awaiting refill
    color: Optional[Tuple[int, int, int]]  # (r,g,b) or None when cleared
