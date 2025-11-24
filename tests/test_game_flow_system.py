import random

from esper import World

from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.game_state import GameMode, GameState
from ecs.components.human_agent import HumanAgent
from ecs.components.starting_ability_choice import AbilityChoice
from ecs.components.starting_skill_choice import SkillChoice
from ecs.events.bus import (
    EVENT_COMBAT_RESET,
    EVENT_COMBAT_START_REQUEST,
    EVENT_DIALOGUE_COMPLETED,
    EVENT_DIALOGUE_START,
    EVENT_MATCH_READY,
    EVENT_MATCH_SETUP_REQUEST,
    EVENT_MENU_NEW_GAME_SELECTED,
    EventBus,
)
from ecs.factories.abilities import create_ability_by_name
from ecs.systems.game_flow_system import GameFlowSystem
from ecs.systems.match_setup_system import MatchSetupSystem
from world import create_world


def _player_entity(world: World) -> int:
    return next(entity for entity, _ in world.get_component(HumanAgent))


def test_new_game_triggers_ability_draft():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False, randomize_enemy=False)
    GameFlowSystem(world, bus, rng=random.Random(0))
    MatchSetupSystem(world, bus, rng=random.Random(1))

    bus.emit(EVENT_MENU_NEW_GAME_SELECTED)

    state = next(comp for _, comp in world.get_component(GameState))
    assert state.mode == GameMode.ABILITY_DRAFT
    ability_choices = list(world.get_component(AbilityChoice))
    assert ability_choices, "Expected an ability draft choice window to be spawned"
    assert not list(world.get_component(SkillChoice)), "Skill draft should wait for ability selection"


def test_combat_reset_spawns_followup_draft_without_duplicates():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False, randomize_enemy=False)
    player_entity = _player_entity(world)
    owner = world.component_for_entity(player_entity, AbilityListOwner)
    owned_ability = create_ability_by_name(world, "tactical_shift")
    owner.ability_entities.append(owned_ability)

    GameFlowSystem(world, bus, rng=random.Random(1))

    captured: dict[str, object] = {}

    def _capture(sender, **payload):
        captured.update(payload)

    bus.subscribe(EVENT_MATCH_SETUP_REQUEST, _capture)

    bus.emit(
        EVENT_COMBAT_RESET,
        reason="enemy_defeated",
        defeated_entity=0,
        next_enemy=world.create_entity(),
    )

    state = next(comp for _, comp in world.get_component(GameState))
    assert state.mode == GameMode.ABILITY_DRAFT
    assert not captured, "Match setup should be deferred until after ability selection"

    offered_names = {choice.ability_name for _, choice in world.get_component(AbilityChoice)}
    assert offered_names, "Expected follow-up ability choices"
    assert "tactical_shift" not in offered_names


def test_new_game_skips_ability_when_unavailable():
    bus = EventBus()
    world = create_world(bus, randomize_enemy=False)
    player_entity = _player_entity(world)
    owner = world.component_for_entity(player_entity, AbilityListOwner)
    owner.ability_entities.append(world.create_entity())

    GameFlowSystem(world, bus, rng=random.Random(2))

    bus.emit(EVENT_MENU_NEW_GAME_SELECTED)

    state = next(comp for _, comp in world.get_component(GameState))
    assert state.mode == GameMode.SKILL_DRAFT
    skill_choices = list(world.get_component(SkillChoice))
    assert skill_choices, "Expected skill draft to start when ability draft is unavailable"


def test_match_ready_transitions_through_dialogue_to_combat():
    bus = EventBus()
    world = create_world(bus, randomize_enemy=False)
    GameFlowSystem(world, bus, rng=random.Random(3))
    player_entity = _player_entity(world)
    enemy_entity = world.create_entity()

    dialogue_payload: dict[str, object] = {}
    combat_payload: dict[str, object] = {}

    bus.subscribe(EVENT_DIALOGUE_START, lambda sender, **payload: dialogue_payload.update(payload))
    bus.subscribe(EVENT_COMBAT_START_REQUEST, lambda sender, **payload: combat_payload.update(payload))

    bus.emit(
        EVENT_MATCH_READY,
        owner_entity=player_entity,
        enemy_entity=enemy_entity,
        dialogue_mode=GameMode.DIALOGUE,
        resume_mode=GameMode.COMBAT,
        fallback_mode=GameMode.COMBAT,
    )

    state = next(comp for _, comp in world.get_component(GameState))
    assert state.mode == GameMode.DIALOGUE
    assert dialogue_payload.get("left_entity") == player_entity
    assert dialogue_payload.get("right_entity") == enemy_entity

    bus.emit(
        EVENT_DIALOGUE_COMPLETED,
        left_entity=player_entity,
        right_entity=enemy_entity,
        resume_mode=GameMode.COMBAT,
    )

    state = next(comp for _, comp in world.get_component(GameState))
    assert state.mode == GameMode.COMBAT
    assert combat_payload.get("player_entity") == player_entity
    assert combat_payload.get("enemy_entity") == enemy_entity
