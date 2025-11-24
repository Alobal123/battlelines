from __future__ import annotations

import json
import random
from pathlib import Path

from esper import World

from ecs.components.game_state import GameMode, GameState
from ecs.components.story_progress_tracker import StoryProgressTracker
from ecs.events.bus import (
    EVENT_ENEMY_DEFEATED,
    EVENT_MENU_CONTINUE_SELECTED,
    EVENT_MENU_NEW_GAME_SELECTED,
    EventBus,
)
from ecs.menu.components import MenuAction, MenuButton
from ecs.menu.factory import spawn_main_menu
from ecs.menu.input_system import MenuInputSystem
from ecs.systems.game_flow_system import GameFlowSystem
from ecs.systems.match_setup_system import MatchSetupSystem
from ecs.systems.skills.skill_pool_system import SkillPoolSystem
from ecs.systems.skills.skill_choice_system import SkillChoiceSystem
from ecs.systems.location_choice_system import LocationChoiceSystem
from ecs.systems.story_progress_system import StoryProgressSystem
from world import create_world


def _get_tracker(world: World) -> StoryProgressTracker:
    entries = list(world.get_component(StoryProgressTracker))
    assert entries, "StoryProgressTracker component expected"
    return entries[0][1]


def test_story_progress_system_tracks_enemy_defeats(tmp_path) -> None:
    world = World()
    bus = EventBus()
    save_path = Path(tmp_path) / "progress.json"
    system = StoryProgressSystem(world, bus, save_path=save_path, load_existing=False)

    bus.emit(EVENT_ENEMY_DEFEATED, entity=42)

    tracker = _get_tracker(world)
    assert tracker.enemies_defeated == 1
    assert system.has_progress is True
    with save_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["enemies_defeated"] == 1


def test_story_progress_system_resets_on_new_game(tmp_path) -> None:
    world = World()
    bus = EventBus()
    save_path = Path(tmp_path) / "progress.json"
    system = StoryProgressSystem(world, bus, save_path=save_path, load_existing=False)

    tracker = _get_tracker(world)
    tracker.enemies_defeated = 5
    system.save_progress()
    assert system.has_progress is True

    bus.emit(EVENT_MENU_NEW_GAME_SELECTED)

    tracker = _get_tracker(world)
    assert tracker.enemies_defeated == 0
    assert system.has_progress is False
    with save_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["enemies_defeated"] == 0


def test_story_progress_system_loads_on_continue(tmp_path) -> None:
    world = World()
    bus = EventBus()
    save_path = Path(tmp_path) / "progress.json"
    system = StoryProgressSystem(world, bus, save_path=save_path, load_existing=False)

    system.reset_progress()
    with save_path.open("w", encoding="utf-8") as handle:
        json.dump({"enemies_defeated": 7}, handle)

    tracker = _get_tracker(world)
    tracker.enemies_defeated = 0
    assert system.has_progress is False

    bus.emit(EVENT_MENU_CONTINUE_SELECTED)

    tracker = _get_tracker(world)
    assert tracker.enemies_defeated == 7
    assert system.has_progress is True


def test_story_progress_tracks_location_completion(tmp_path) -> None:
    world = World()
    bus = EventBus()
    save_path = Path(tmp_path) / "progress.json"
    StoryProgressSystem(world, bus, save_path=save_path, load_existing=False)

    tracker = _get_tracker(world)
    tracker.current_location_slug = "graveyard"
    tracker.current_location_enemies_defeated = 2

    bus.emit(EVENT_ENEMY_DEFEATED, entity=101)

    tracker = _get_tracker(world)
    assert tracker.locations_completed == 1
    assert tracker.current_location_enemies_defeated == 0
    with save_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["locations_completed"] == 1


def test_spawn_main_menu_continue_button_state(tmp_path) -> None:
    world = World()
    bus = EventBus()
    world.create_entity(GameState(mode=GameMode.MENU))

    # Case 1: continue disabled when no progress
    spawn_main_menu(world, 800, 600, enable_continue=False)
    buttons = {button.action: button for _, button in world.get_component(MenuButton)}
    continue_button = buttons.get(MenuAction.CONTINUE)
    new_game_button = buttons.get(MenuAction.NEW_GAME)
    assert continue_button is not None and continue_button.enabled is False
    assert new_game_button is not None and new_game_button.enabled is True

    # Clear menu entities and regenerate with progress
    for ent, _ in list(world.get_component(MenuButton)):
        world.delete_entity(ent)

    world.create_entity(StoryProgressTracker(enemies_defeated=3))
    spawn_main_menu(world, 800, 600)
    buttons = {button.action: button for _, button in world.get_component(MenuButton)}
    continue_button = buttons.get(MenuAction.CONTINUE)
    assert continue_button is not None and continue_button.enabled is True


def test_menu_continue_button_ignored_when_disabled(tmp_path) -> None:
    world = World()
    bus = EventBus()
    world.create_entity(GameState(mode=GameMode.MENU))
    spawn_main_menu(world, 800, 600, enable_continue=False)
    system = MenuInputSystem(world, bus)

    triggered = {"continue": False}
    bus.subscribe(EVENT_MENU_CONTINUE_SELECTED, lambda sender, **_: triggered.__setitem__("continue", True))

    # Find the disabled continue button and simulate a click on it.
    for _, button in world.get_component(MenuButton):
        if button.action == MenuAction.CONTINUE:
            system.handle_mouse_press(button.x, button.y, 1, press_id=501)
            break

    state_entries = list(world.get_component(GameState))
    assert state_entries
    state = state_entries[0][1]
    assert state.mode == GameMode.MENU
    assert triggered["continue"] is False


def test_menu_new_game_emits_event_and_changes_mode(tmp_path) -> None:
    bus = EventBus()
    world = create_world(
        bus,
        initial_mode=GameMode.MENU,
        grant_default_player_abilities=False,
        randomize_enemy=False,
    )
    spawn_main_menu(world, 800, 600, enable_continue=False)
    GameFlowSystem(world, bus, rng=random.Random(0))
    MatchSetupSystem(world, bus, rng=random.Random(1))
    SkillPoolSystem(world, bus, rng=random.Random(2))
    SkillChoiceSystem(world, bus)
    LocationChoiceSystem(world, bus)
    system = MenuInputSystem(world, bus)

    fired = {"new_game": False}
    bus.subscribe(EVENT_MENU_NEW_GAME_SELECTED, lambda sender, **_: fired.__setitem__("new_game", True))

    for _, button in world.get_component(MenuButton):
        if button.action == MenuAction.NEW_GAME:
            system.handle_mouse_press(button.x, button.y, 1, press_id=601)
            break

    state_entries = list(world.get_component(GameState))
    assert state_entries
    state = state_entries[0][1]
    assert state.mode == GameMode.ABILITY_DRAFT
    assert fired["new_game"] is True
