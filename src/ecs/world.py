from esper import World
from .events.bus import EventBus
from ecs.components.human_agent import HumanAgent
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.tile_bank import TileBank
from ecs.systems.board import COLOR_NAME_MAP  # testing prefill of bank; consider extracting constants later

def create_world(event_bus: EventBus) -> World:
    world = World()
    # Create multiple ability entities
    ability_shift = world.create_entity(
        Ability(name="tactical_shift", kind="active", cost={"red": 3, "blue": 2}, params={"target_color": "red"}),
        AbilityTarget(target_type="tile", max_targets=1),
    )
    ability_pulse = world.create_entity(
        Ability(name="crimson_pulse", kind="active", cost={"red": 5}),
        AbilityTarget(target_type="tile", max_targets=1),
    )
    # Create player entity with HumanAgent and AbilityListOwner
    player_ent = world.create_entity(
        HumanAgent(),
        AbilityListOwner(ability_entities=[ability_shift, ability_pulse]),
        TileBank(owner_entity=0)
    )
    # Reset owner_entity of bank to actual player entity id (created above, initially 0 placeholder)
    bank = world.component_for_entity(player_ent, TileBank)
    bank.owner_entity = player_ent
    # TESTING: Prefill bank with 100 of each tile type name so abilities can be freely tested.
    # This introduces a dependency on BoardSystem constants; for production consider moving tile type names to a shared constants module.
    for type_name in COLOR_NAME_MAP.values():
        bank.counts[type_name] = 100
    return world
