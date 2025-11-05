from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass(slots=True)
class TileType:
    """Represents the logical type of a tile (e.g., 'tactics', 'orders', 'morale').

    color_name: textual name used for rendering choice; raw_color stores original RGB tuple for
    legacy logic/tests that still rely on color tuple equality. Setting color via the compatibility
    property updates raw_color and (if color_name not manually set) derives a synthetic color_name.
    Clearing a tile sets raw_color and color_name to None.
    """
    type_name: str
    color_name: Optional[str]
    raw_color: Optional[Tuple[int,int,int]]

    # Provides .color property for simplified RGB access.
    @property
    def color(self) -> Optional[Tuple[int,int,int]]:
        return self.raw_color

    @color.setter
    def color(self, value: Optional[Tuple[int,int,int]]):
        self.raw_color = value
        if value is None:
            self.color_name = None
        else:
            # Only auto-derive if not explicitly set already
            if not self.color_name:
                r,g,b = value
                self.color_name = f"{r}_{g}_{b}"

# Alias removed: prefer importing TileType directly.
