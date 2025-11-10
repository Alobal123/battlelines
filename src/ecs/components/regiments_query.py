from typing import List, Tuple
from esper import World
from .regiment import Regiment

def get_regiments(world: World) -> List[Tuple[int, Regiment]]:
    """Return all regiment entities and components."""
    return list(world.get_component(Regiment))

def get_regiments_for_owner(world: World, owner_entity: int) -> List[Tuple[int, Regiment]]:
    """Return regiments whose Regiment.owner_id matches owner_entity."""
    return [(ent, reg) for ent, reg in world.get_component(Regiment) if reg.owner_id == owner_entity]
