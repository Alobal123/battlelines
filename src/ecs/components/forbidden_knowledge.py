from dataclasses import dataclass


@dataclass(slots=True)
class ForbiddenKnowledge:
    """Tracks global forbidden knowledge progress accrued from Secrets matches."""

    value: int = 0
    max_value: int = 20
    chaos_released: bool = False
