from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Effect:
    """Represents a status or rule modifier that applies to a single owner entity.

    The effect entity will typically also carry duration or trigger components
    that systems can inspect to determine when it should expire.
    """

    slug: str
    owner_entity: int
    source_entity: int | None = None
    stacks: bool = False
    stack_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
