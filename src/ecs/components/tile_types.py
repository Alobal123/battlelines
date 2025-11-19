from dataclasses import dataclass, field
from typing import Dict, Iterable, Tuple, List

@dataclass(slots=True)
class TileTypes:
    """Canonical tile type definitions stored on a single entity.

    This component lives alongside TileTypeRegistry (tag) and provides mapping utilities.
    """
    types: Dict[str, Tuple[int,int,int]]
    spawnable: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.spawnable:
            # Preserve order while filtering unknown types.
            seen: set[str] = set()
            filtered: List[str] = []
            for name in self.spawnable:
                if name in self.types and name not in seen:
                    filtered.append(name)
                    seen.add(name)
            self.spawnable = filtered or list(self.types.keys())
        else:
            self.spawnable = list(self.types.keys())

    def background_for(self, type_name: str) -> Tuple[int,int,int]:
        return self.types[type_name]

    def all_types(self) -> List[str]:
        return self.spawnable_types()

    def spawnable_types(self) -> List[str]:
        return list(self.spawnable)

    def defined_types(self) -> List[str]:
        return list(self.types.keys())

    def set_spawnable(self, type_names: Iterable[str], *, allow_empty: bool = False) -> None:
        seen: set[str] = set()
        filtered: List[str] = []
        for name in type_names:
            if name in self.types and name not in seen:
                filtered.append(name)
                seen.add(name)
        if not filtered and not allow_empty:
            filtered = list(self.types.keys())
        self.spawnable = filtered

    def enable_type(self, type_name: str) -> None:
        if type_name in self.types and type_name not in self.spawnable:
            self.spawnable.append(type_name)

    def disable_type(self, type_name: str, *, allow_empty: bool = False) -> None:
        self.spawnable = [name for name in self.spawnable if name != type_name]
        if not self.spawnable and not allow_empty:
            self.spawnable = list(self.types.keys())

    def register_type(self, type_name: str, color: Tuple[int, int, int], *, spawnable: bool = True) -> None:
        self.types[type_name] = color
        if spawnable:
            self.enable_type(type_name)
        elif type_name in self.spawnable:
            self.spawnable = [name for name in self.spawnable if name != type_name]
