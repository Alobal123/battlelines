from dataclasses import dataclass

@dataclass(slots=True)
class TileTypeRegistry:
    """Empty tag component marking the single entity that stores canonical tile type definitions.

    The same entity will also have a TileTypes component containing the mapping of type_name -> color.
    """
    pass
