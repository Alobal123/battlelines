from dataclasses import dataclass

@dataclass(slots=True)
class ActiveTurn:
    """Marks which owner entity currently has the active turn for attributing clears.

    owner_entity: entity id of the player whose actions (swaps, ability effects) should credit their TileBank.
    """
    owner_entity: int