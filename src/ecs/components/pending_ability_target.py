from dataclasses import dataclass


@dataclass(slots=True)
class PendingAbilityTarget:
    ability_entity: int
    owner_entity: int
    row: int | None = None
    col: int | None = None
    target_entity: int | None = None