from dataclasses import dataclass, field
from typing import List

@dataclass(slots=True)
class TurnOrder:
    """Stores ordered list of owner entities and current index."""
    owners: List[int] = field(default_factory=list)
    index: int = 0

    def current(self) -> int | None:
        if not self.owners:
            return None
        return self.owners[self.index % len(self.owners)]

    def advance(self):
        if self.owners:
            self.index = (self.index + 1) % len(self.owners)
