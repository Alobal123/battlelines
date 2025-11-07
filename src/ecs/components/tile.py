from dataclasses import dataclass

@dataclass(slots=True)
class TileType:
    """Per-tile type assignment (no color data).

    Stores only the semantic type_name. Active/empty state is handled by ActiveSwitch.
    Canonical color lookup resides in the singleton entity with TileTypeRegistry + TileTypes.
    """
    type_name: str


