from dataclasses import dataclass
from typing import Tuple, Optional

@dataclass
class SwapAnimation:
    src: Tuple[int,int]
    dst: Tuple[int,int]
    progress: float = 0.0  # 0..1 forward or reverse
    phase: str = 'forward'  # 'forward' or 'reverse'
    valid: Optional[bool] = None  # validity outcome once known
