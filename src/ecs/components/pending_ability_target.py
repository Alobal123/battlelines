from dataclasses import dataclass

@dataclass(slots=True)
class PendingAbilityTarget:
    ability_entity: int
    owner_entity: int
    row: int
    col: int