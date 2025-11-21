import random

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
from ecs.components.forbidden_knowledge import ForbiddenKnowledge
from ecs.effects.factory import ensure_default_effects_registered
from ecs.components.health import Health
from ecs.factories.abilities import create_default_player_abilities
from ecs.factories.enemies import create_enemy_undead_gardener
from ecs.components.skill_list_owner import SkillListOwner
from ecs.factories.player_skills import create_skill_self_reprimand
from ecs.components.affinity import Affinity


def create_world(
    event_bus: EventBus,
    initial_mode: GameMode = GameMode.COMBAT,
    *,
    grant_default_player_abilities: bool = False,
    grant_default_player_skills: bool = False,
    randomize_enemy: bool = False,
    rng: random.Random | None = None,
) -> World:
    world = World()
    setattr(world, "random", rng or random.Random())

    # Register or update the global game state resource.
    state_entity = world.create_entity()
    world.add_component(state_entity, GameState(mode=initial_mode))
    world.add_component(state_entity, ForbiddenKnowledge())
    
    # Register core effect definitions if not already present.
    ensure_default_effects_registered()

    # Player 1 (human)
    abilities_p1 = create_default_player_abilities(world) if grant_default_player_abilities else []
    player1_ent = world.create_entity(
        HumanAgent(),
        AbilityListOwner(ability_entities=abilities_p1),
        SkillListOwner(),
        TileBank(owner_entity=0),
        Health(current=30, max_hp=30),
        Affinity(base={"blood": 1, "spirit": 1}),
        Character(
            slug="fiora",
            name="Fiora",
            description="A young witch mastering the arcane arts",
            portrait_path="fiora.png"
        ),
    )
    bank1 = world.component_for_entity(player1_ent, TileBank)
    bank1.owner_entity = player1_ent
    if grant_default_player_skills:
        try:
            base_skill = create_skill_self_reprimand(world)
        except Exception:
            base_skill = None
        if base_skill is not None:
            skill_owner = world.component_for_entity(player1_ent, SkillListOwner)
            skill_owner.skill_entities.append(base_skill)
    from ecs.systems.enemy_pool_system import EnemyPoolSystem

    enemy_pool = EnemyPoolSystem(world, event_bus, rng=getattr(world, "random", None))
    setattr(world, "enemy_pool", enemy_pool)
    player2_ent: int | None
    if randomize_enemy:
        player2_ent = enemy_pool.spawn_random_enemy()
    else:
        try:
            player2_ent = enemy_pool.create_enemy("undead_gardener")
        except ValueError:
            player2_ent = enemy_pool.spawn_random_enemy()
    if player2_ent is None:
        player2_ent = create_enemy_undead_gardener(world, max_hp=30)

    # Ensure the enemy ability component is processed after the player's so tests and
    # systems that iterate owners meet the human abilities first.
    enemy_abilities = world.component_for_entity(player2_ent, AbilityListOwner)
    world.remove_component(player2_ent, AbilityListOwner)
    world.add_component(player2_ent, enemy_abilities)
    if not world.has_component(player2_ent, SkillListOwner):
        world.add_component(player2_ent, SkillListOwner())
    if not world.has_component(player2_ent, Affinity):
        world.add_component(player2_ent, Affinity(base={}))


    # Create single registry entity with canonical types
    registry_entity = world.create_entity(
        TileTypeRegistry(),
        TileTypes(
            types={
                'nature':      (63, 127, 59),    # #3F7F3B
                'blood':       (179, 18, 42),    # #B3122A
                'shapeshift':  (216, 155, 38),   # #D89B26
                'spirit':      (165, 139, 234),  # #A58BEA
                'hex':         (123, 62, 133),   # #7B3E85
                'secrets':     (232, 215, 161),  # #E8D7A1
                'witchfire':   (226, 62, 160),   # #E23EA0
                'chaos':       (64, 196, 112),   # poisonous green tint for chaos
            },
            spawnable=[
                'nature', 'blood', 'shapeshift', 'spirit', 'hex', 'secrets', 'witchfire'
            ],
        ),
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
