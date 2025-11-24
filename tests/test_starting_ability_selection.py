import random

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.game_state import GameMode, GameState
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.turn_order import TurnOrder
from ecs.components.starting_ability_choice import AbilityChoice
from ecs.components.starting_skill_choice import SkillChoice
from ecs.components.skill import Skill
from ecs.components.skill_list_owner import SkillListOwner
from ecs.components.location import CurrentLocation, LocationChoice
from ecs.components.choice_window import ChoiceWindow
from ecs.components.dialogue_session import DialogueSession
from ecs.events.bus import EVENT_CHOICE_SELECTED, EVENT_MATCH_SETUP_REQUEST, EventBus
from ecs.factories.abilities import spawn_player_ability_choice
from ecs.factories.skills import skill_slugs_for_entity
from ecs.factories.locations import get_location_spec
from ecs.systems.game_flow_system import GameFlowSystem
from ecs.systems.match_setup_system import MatchSetupSystem
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.dialogue_system import DialogueSystem
from ecs.systems.skills.skill_pool_system import SkillPoolSystem
from ecs.systems.skills.skill_choice_system import SkillChoiceSystem
from ecs.systems.location_choice_system import LocationChoiceSystem
from ecs.systems.skills.apply_skill_effects_system import ApplySkillEffectsSystem
from ecs.utils.combatants import find_primary_opponent
from world import create_world

from tests.helpers import grant_player_skills


def _human_entity(world: World) -> int:
    return next(ent for ent, _ in world.get_component(HumanAgent))


def test_spawn_player_ability_choice_creates_options():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    grant_player_skills(world, ("self_reprimand",))
    window_entity = spawn_player_ability_choice(
        world,
        rng=random.Random(0),
        require_empty_owner=True,
        title="Choose Your First Ability",
    )
    assert window_entity is not None
    choices = list(world.get_component(AbilityChoice))
    assert len(choices) == 3
    state = next(comp for _, comp in world.get_component(GameState))
    assert state.mode == GameMode.ABILITY_DRAFT


def test_player_ability_selection_adds_chosen_ability():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    grant_player_skills(world, ("self_reprimand",))
    DialogueSystem(world, bus)
    AbilitySystem(world, bus)
    GameFlowSystem(world, bus, rng=random.Random(42))
    MatchSetupSystem(world, bus, rng=random.Random(1))
    SkillPoolSystem(world, bus, rng=random.Random(2))
    SkillChoiceSystem(world, bus)
    LocationChoiceSystem(world, bus)
    ApplySkillEffectsSystem(world, bus)
    window_entity = spawn_player_ability_choice(
        world,
        rng=random.Random(1),
        require_empty_owner=True,
        title="Choose Your First Ability",
    )
    state = next(comp for _, comp in world.get_component(GameState))
    assert state.mode == GameMode.ABILITY_DRAFT
    choices = list(world.get_component(AbilityChoice))
    assert choices, "Expected at least one starting ability option"
    choice_entity, choice_comp = choices[0]
    selected_name = choice_comp.ability_name
    owner_entity = _human_entity(world)
    skill_owner: SkillListOwner = world.component_for_entity(owner_entity, SkillListOwner)
    initial_skill_count = len(skill_owner.skill_entities)
    bus.emit(
        EVENT_CHOICE_SELECTED,
        window_entity=window_entity,
        choice_entity=choice_entity,
        press_id=777,
    )
    assert state.mode == GameMode.SKILL_DRAFT
    owner_comp: AbilityListOwner = world.component_for_entity(owner_entity, AbilityListOwner)
    assert len(owner_comp.ability_entities) == 1
    ability_entity = owner_comp.ability_entities[0]
    ability = world.component_for_entity(ability_entity, Ability)
    assert ability.name == selected_name
    assert not list(world.get_component(AbilityChoice))
    skill_choices = list(world.get_component(SkillChoice))
    assert skill_choices, "Expected skill options after selecting an ability"
    skill_choice_entity, skill_choice = skill_choices[0]
    # Locate the skill choice window that owns this option.
    skill_window_entity = next(
        (
            window_ent
            for window_ent, window in world.get_component(ChoiceWindow)
            if skill_choice_entity in window.option_entities
        ),
        None,
    )
    assert skill_window_entity is not None

    bus.emit(
        EVENT_CHOICE_SELECTED,
        window_entity=skill_window_entity,
        choice_entity=skill_choice_entity,
        press_id=888,
    )

    assert state.mode == GameMode.LOCATION_DRAFT

    location_choices = list(world.get_component(LocationChoice))
    assert location_choices, "Expected location options after selecting a skill"
    location_choice_entity, location_choice = location_choices[0]
    location_window_entity = next(
        (
            window_ent
            for window_ent, window in world.get_component(ChoiceWindow)
            if location_choice_entity in window.option_entities
        ),
        None,
    )
    assert location_window_entity is not None

    bus.emit(
        EVENT_CHOICE_SELECTED,
        window_entity=location_window_entity,
        choice_entity=location_choice_entity,
        press_id=999,
    )

    assert state.mode == GameMode.DIALOGUE

    current_location = world.component_for_entity(owner_entity, CurrentLocation)
    assert current_location.slug == location_choice.location_slug
    spec = get_location_spec(current_location.slug)
    assert spec is not None
    assert set(current_location.enemy_names) == set(spec.enemy_names)

    assert len(skill_owner.skill_entities) == initial_skill_count + 1
    gained_skill_entity = skill_owner.skill_entities[-1]
    _ = world.component_for_entity(gained_skill_entity, Skill)
    assert skill_choice.skill_name in skill_slugs_for_entity(world, gained_skill_entity)

    sessions = list(world.get_component(DialogueSession))
    assert sessions
    _, session = sessions[0]
    assert session.current_index == 0


def test_match_setup_uses_chosen_enemy_for_combat():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False, randomize_enemy=False)
    DialogueSystem(world, bus)
    GameFlowSystem(world, bus, rng=random.Random(5))
    MatchSetupSystem(world, bus, rng=random.Random(2))

    player_entity = _human_entity(world)
    existing_enemies = [ent for ent, _ in world.get_component(RuleBasedAgent)]
    assert existing_enemies, "Expected a pre-existing enemy"

    enemy_pool = getattr(world, "enemy_pool")
    replacement_enemy = enemy_pool.create_enemy("undead_beekeeper")

    bus.emit(
        EVENT_MATCH_SETUP_REQUEST,
        owner_entity=player_entity,
        enemy_entity=replacement_enemy,
        press_id=123,
    )

    assert find_primary_opponent(world, player_entity) == replacement_enemy

    remaining_enemies = [ent for ent, _ in world.get_component(RuleBasedAgent)]
    assert remaining_enemies == [replacement_enemy]

    orders = list(world.get_component(TurnOrder))
    assert orders
    _, order = orders[0]
    assert order.owners == [player_entity, replacement_enemy]
