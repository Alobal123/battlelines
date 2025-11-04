from dataclasses import dataclass
from typing import Tuple

@dataclass
class FadeAnimation:
    pos: Tuple[int,int]
    alpha: float = 1.0
