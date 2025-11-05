from dataclasses import dataclass

@dataclass(slots=True)
class AbilityTarget:
    """Targeting specification for an ability.

    target_type: category of target (e.g., 'tile', 'entity', 'area').
    max_targets: maximum number of selectable targets for this activation.
    """
    target_type: str
    max_targets: int
