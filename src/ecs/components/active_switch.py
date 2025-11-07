from dataclasses import dataclass

@dataclass(slots=True)
class ActiveSwitch:
    """Per-tile occupancy flag.

    active: True if the cell currently holds a tile type; False if cleared/empty.
    Type information now lives in a separate TileType component.
    """
    active: bool = True
