from esper import World
from .events.bus import EventBus
from ecs.components.human_agent import HumanAgent
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.tile_bank import TileBank
from ecs.components.tile_type_registry import TileTypeRegistry
from ecs.components.tile_types import TileTypes
from ecs.components.character import Character
from ecs.components.game_state import GameState, GameMode
from ecs.effects.registry import EffectDefinition, default_effect_registry, register_effect
from ecs.components.health import Health
from ecs.factories.abilities import create_default_player_abilities
from ecs.factories.enemies import create_enemy_undead_gardener


def create_world(
    event_bus: EventBus,
    initial_mode: GameMode = GameMode.COMBAT,
    *,
    grant_default_player_abilities: bool = True,
) -> World:
    world = World()

    # Register or update the global game state resource.
    state_entity = world.create_entity()
    world.add_component(state_entity, GameState(mode=initial_mode))
    
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
    abilities_p1 = create_default_player_abilities(world) if grant_default_player_abilities else []
    player1_ent = world.create_entity(
        HumanAgent(),
        AbilityListOwner(ability_entities=abilities_p1),
        TileBank(owner_entity=0),
        Health(current=30, max_hp=30),
        Character(
            slug="fiora",
            name="Fiora",
            description="A young witch mastering the arcane arts",
            portrait_path="fiora.png"
        ),
    )
    bank1 = world.component_for_entity(player1_ent, TileBank)
    bank1.owner_entity = player1_ent
    player2_ent = create_enemy_undead_gardener(world)

    # Ensure the enemy ability component is processed after the player's so tests and
    # systems that iterate owners meet the human abilities first.
    enemy_abilities = world.component_for_entity(player2_ent, AbilityListOwner)
    world.remove_component(player2_ent, AbilityListOwner)
    world.add_component(player2_ent, enemy_abilities)


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
    return world


def initialize_combat_entities(world: World) -> tuple[int, int]:
    """Compatibility helper returning the player entity ids.

    Historical tests expect this function, so we look up the primary player
    entities that were created during ``create_world`` and return them.
    """
    human_entities = [entity for entity, _ in world.get_component(HumanAgent)]
    ai_entities = [entity for entity, _ in world.get_component(RuleBasedAgent)]
    if not human_entities or not ai_entities:
        return tuple()
    return human_entities[0], ai_entities[0]
