from dataclasses import dataclass


@dataclass(slots=True)
class EffectDuration:
    """Tracks effect duration in turn counts rather than seconds."""

    remaining_turns: int
