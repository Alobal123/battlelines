from dataclasses import dataclass
from typing import Tuple

@dataclass(slots=True)
class FallAnimation:
    src: Tuple[int,int]
    dst: Tuple[int,int]
    color: Tuple[int,int,int]
    linear: float = 0.0  # 0..1
