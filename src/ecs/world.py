from esper import World
from .events.bus import EventBus
from ecs.components.human_agent import HumanAgent
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.tile_bank import TileBank
from ecs.components.tile_type_registry import TileTypeRegistry
from ecs.components.tile_types import TileTypes
from ecs.effects.registry import EffectDefinition, default_effect_registry, register_effect
from ecs.components.health import Health


def create_world(event_bus: EventBus) -> World:
    world = World()
    # THEME: Transitioning from army combat to witch school.
    # Previous regiment/army abstractions retained temporarily; new tile types below reflect magical faculties.
    # Future refactor: replace Regiment/ArmyRoster with House/Circle components.
    if not default_effect_registry.has("morale_boost"):
        register_effect(
            EffectDefinition(
                slug="morale_boost",
                display_name="Bolster Morale",
                description="Temporarily increases a regiment's morale.",
                tags=("morale", "buff"),
                default_metadata={"morale_bonus": 20, "turns": 3},
            )
        )
    # Shared spell definitions (each owner gets its own instances)
    def make_abilities():
        ability_shift = world.create_entity(
            Ability(name="tactical_shift", kind="active", cost={"hex": 3, "nature": 2}, params={"target_color": "hex"}),
            AbilityTarget(target_type="tile", max_targets=1),
        )
        ability_pulse = world.create_entity(
            Ability(name="crimson_pulse", kind="active", cost={"hex": 5}),
            AbilityTarget(target_type="tile", max_targets=1),
        )
        ability_focus = world.create_entity(
            Ability(
                name="bolster_focus",
                kind="active",
                cost={"spirit": 3},
                params={"focus_bonus": 20, "turns": 3},
            ),
            AbilityTarget(target_type="entity", max_targets=1),
        )
        return [ability_shift, ability_pulse, ability_focus]

    # Player 1 (human)
    abilities_p1 = make_abilities()
    player1_ent = world.create_entity(
        HumanAgent(),
        AbilityListOwner(ability_entities=abilities_p1),
        TileBank(owner_entity=0),
        Health(current=30, max_hp=30),
    )
    bank1 = world.component_for_entity(player1_ent, TileBank)
    bank1.owner_entity = player1_ent
    # Player 2 (adversary placeholder; reuse HumanAgent for now until AI component added)
    abilities_p2 = make_abilities()
    player2_ent = world.create_entity(
        HumanAgent(),
        AbilityListOwner(ability_entities=abilities_p2),
        TileBank(owner_entity=0),
        Health(current=30, max_hp=30),
    )
    bank2 = world.component_for_entity(player2_ent, TileBank)
    bank2.owner_entity = player2_ent

    # Removed regiment creation; future: create Houses/Circles here.

    # Create single registry entity with canonical types
    registry_entity = world.create_entity(
        TileTypeRegistry(),
        TileTypes(types={
            'nature':      (63, 127, 59),    # #3F7F3B
            'blood':       (179, 18, 42),    # #B3122A
            'shapeshift':  (216, 155, 38),   # #D89B26
            'spirit':      (165, 139, 234),  # #A58BEA
            'hex':         (123, 62, 133),   # #7B3E85
            'secrets':     (232, 215, 161),  # #E8D7A1
            'witchfire':   (226, 62, 160),   # #E23EA0
        })
    )
    # TESTING: Prefill both banks generously with all type names
    definitions: TileTypes = world.component_for_entity(
        registry_entity, TileTypes)
    for type_name in definitions.types.keys():
        bank1.counts[type_name] = 100
        bank2.counts[type_name] = 100
    return world
