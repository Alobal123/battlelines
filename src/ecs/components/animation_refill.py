from dataclasses import dataclass
from typing import Tuple

@dataclass(slots=True)
class RefillAnimation:
    pos: Tuple[int,int]
    linear: float = 0.0
