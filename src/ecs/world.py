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
    # Shared ability definitions (each owner gets its own instances for independent pending targeting/components)
    def make_abilities():
        ability_shift = world.create_entity(
            Ability(name="tactical_shift", kind="active", cost={"red": 3, "blue": 2}, params={"target_color": "red"}),
            AbilityTarget(target_type="tile", max_targets=1),
        )
        ability_pulse = world.create_entity(
            Ability(name="crimson_pulse", kind="active", cost={"red": 5}),
            AbilityTarget(target_type="tile", max_targets=1),
        )
        return [ability_shift, ability_pulse]

    # Player 1 (human)
    abilities_p1 = make_abilities()
    player1_ent = world.create_entity(
        HumanAgent(),
        AbilityListOwner(ability_entities=abilities_p1),
        TileBank(owner_entity=0)
    )
    bank1 = world.component_for_entity(player1_ent, TileBank)
    bank1.owner_entity = player1_ent
    # Player 2 (adversary placeholder; reuse HumanAgent for now until AI component added)
    abilities_p2 = make_abilities()
    player2_ent = world.create_entity(
        HumanAgent(),
        AbilityListOwner(ability_entities=abilities_p2),
        TileBank(owner_entity=0)
    )
    bank2 = world.component_for_entity(player2_ent, TileBank)
    bank2.owner_entity = player2_ent

    # TESTING: Prefill both banks generously
    for type_name in COLOR_NAME_MAP.values():
        bank1.counts[type_name] = 100
        bank2.counts[type_name] = 100
    return world
