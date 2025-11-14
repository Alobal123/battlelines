from dataclasses import dataclass


@dataclass(slots=True)
class AbilityCooldown:
    """Tracks per-ability cooldown state in turns remaining."""

    remaining_turns: int = 0
