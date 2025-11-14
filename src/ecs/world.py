from esper import World
from .events.bus import EventBus
from ecs.components.human_agent import HumanAgent
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.tile_bank import TileBank
from ecs.components.tile_type_registry import TileTypeRegistry
from ecs.components.tile_types import TileTypes
from ecs.effects.registry import EffectDefinition, default_effect_registry, register_effect
from ecs.components.health import Health
from ecs.factories.abilities import create_default_player_abilities


def create_world(event_bus: EventBus) -> World:
    world = World()
    # THEME: Transitioning from army combat to witch school.
    # Previous regiment/army abstractions retained temporarily; new tile types below reflect magical faculties.
    # Future refactor: replace Regiment/ArmyRoster with House/Circle components.
    
    # Register core effect definitions if not already present.
    if not default_effect_registry.has("damage"):
        register_effect(
            EffectDefinition(
                slug="damage",
                display_name="Damage",
                description="Applies damage when triggered.",
                default_metadata={
                    "amount": 0,
                    "reason": "effect",
                    "source_owner": None,
                    "turns": 0,
                },
            )
        )
    if not default_effect_registry.has("heal"):
        register_effect(
            EffectDefinition(
                slug="heal",
                display_name="Heal",
                description="Applies healing when triggered.",
                default_metadata={
                    "amount": 0,
                    "reason": "effect",
                    "source_owner": None,
                    "turns": 0,
                },
            )
        )
    if not default_effect_registry.has("board_clear_area"):
        register_effect(
            EffectDefinition(
                slug="board_clear_area",
                display_name="Clear Tiles",
                description="Removes tiles in an area, triggering cascades.",
                default_metadata={
                    "shape": "square",
                    "radius": 0,
                    "reason": "effect",
                },
            )
        )
    if not default_effect_registry.has("board_transform_type"):
        register_effect(
            EffectDefinition(
                slug="board_transform_type",
                display_name="Transform Tiles",
                description="Converts tiles of a given type to another type.",
                default_metadata={
                    "target_type": "",
                    "reason": "effect",
                },
            )
        )
    if not default_effect_registry.has("damage_bonus"):
        register_effect(
            EffectDefinition(
                slug="damage_bonus",
                display_name="Damage Bonus",
                description="Increases damage dealt by the owner.",
                default_metadata={
                    "bonus": 1,
                    "reason": "damage_bonus",
                    "stack_key": "damage_bonus",
                },
            )
        )

    # Player 1 (human)
    abilities_p1 = create_default_player_abilities(world)
    player1_ent = world.create_entity(
        HumanAgent(),
        AbilityListOwner(ability_entities=abilities_p1),
        TileBank(owner_entity=0),
        Health(current=30, max_hp=30),
    )
    bank1 = world.component_for_entity(player1_ent, TileBank)
    bank1.owner_entity = player1_ent
    # Player 2 (adversary placeholder; reuse HumanAgent for now until AI component added)
    abilities_p2 = create_default_player_abilities(world)
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
