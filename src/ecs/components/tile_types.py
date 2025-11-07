from dataclasses import dataclass
from typing import Dict, Tuple, List

@dataclass(slots=True)
class TileTypes:
    """Canonical tile type definitions stored on a single entity.

    This component lives alongside TileTypeRegistry (tag) and provides mapping utilities.
    """
    types: Dict[str, Tuple[int,int,int]]

    def background_for(self, type_name: str) -> Tuple[int,int,int]:
        return self.types[type_name]

    def all_types(self) -> List[str]:
        return list(self.types.keys())
