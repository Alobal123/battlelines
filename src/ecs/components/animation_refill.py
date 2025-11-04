from dataclasses import dataclass
from typing import Tuple

@dataclass
class RefillAnimation:
    pos: Tuple[int,int]
    linear: float = 0.0
