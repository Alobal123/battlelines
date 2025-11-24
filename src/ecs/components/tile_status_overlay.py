from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass(slots=True)
class TileStatusOverlay:
    """Visual overlay metadata for tiles affected by lingering effects."""

    slug: str
    effect_entity: int
    icon_key: Optional[str] = None
    tint: Optional[Tuple[int, int, int]] = None
    metadata: Dict[str, object] = field(default_factory=dict)
