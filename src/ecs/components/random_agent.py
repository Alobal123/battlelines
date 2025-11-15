from dataclasses import dataclass


@dataclass(slots=True)
class RandomAgent:
    """Marker component for a simple random-action AI controller."""

    seed: int | None = None
    decision_delay: float = 0.0
    selection_delay: float = 0.0
