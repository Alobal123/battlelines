from dataclasses import dataclass


@dataclass(slots=True)
class RuleBasedAgent:
    """Marker component for the rule-driven AI controller."""

    decision_delay: float = 0.8
    selection_delay: float = 0.4
