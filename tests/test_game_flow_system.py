import random

from esper import World

from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.choice_window import ChoiceWindow
from ecs.components.game_state import GameMode, GameState
from ecs.components.human_agent import HumanAgent
from ecs.components.starting_ability_choice import AbilityChoice
from ecs.events.bus import (
    EVENT_COMBAT_RESET,
    EVENT_MATCH_SETUP_REQUEST,
    EVENT_MENU_NEW_GAME_SELECTED,
    EventBus,
)
from ecs.factories.abilities import create_ability_by_name
from ecs.systems.game_flow_system import GameFlowSystem
from ecs.world import create_world


def _player_entity(world: World) -> int:
    return next(entity for entity, _ in world.get_component(HumanAgent))


def test_new_game_triggers_ability_draft():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False, randomize_enemy=False)
    GameFlowSystem(world, bus, rng=random.Random(0))

    bus.emit(EVENT_MENU_NEW_GAME_SELECTED)

    state = next(comp for _, comp in world.get_component(GameState))
    assert state.mode == GameMode.ABILITY_DRAFT
    windows = list(world.get_component(ChoiceWindow))
    assert windows, "Expected an ability draft choice window to be spawned"


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


def test_new_game_without_draft_requests_match():
    bus = EventBus()
    world = create_world(bus, randomize_enemy=False)
    player_entity = _player_entity(world)
    owner = world.component_for_entity(player_entity, AbilityListOwner)
    owner.ability_entities.append(world.create_entity())

    GameFlowSystem(world, bus, rng=random.Random(2))

    captured: dict[str, object] = {}

    def _capture(sender, **payload):
        captured.update(payload)

    bus.subscribe(EVENT_MATCH_SETUP_REQUEST, _capture)

    bus.emit(EVENT_MENU_NEW_GAME_SELECTED)
    assert captured.get("owner_entity") == player_entity
    assert str(captured.get("reason", "")).startswith("new_game")
