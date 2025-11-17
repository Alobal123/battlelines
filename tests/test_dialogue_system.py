from __future__ import annotations

from esper import World

from ecs.components.dialogue_session import DialogueSession
from ecs.components.game_state import GameMode, GameState
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.events.bus import (
    EVENT_DIALOGUE_COMPLETED,
    EVENT_DIALOGUE_START,
    EVENT_MOUSE_PRESS,
    EventBus,
)
from ecs.systems.dialogue_system import DialogueSystem
from ecs.world import create_world


def _get_state(world: World) -> GameState:
    entries = list(world.get_component(GameState))
    assert entries
    return entries[0][1]


def _get_dialogue_session(world: World):
    sessions = list(world.get_component(DialogueSession))
    return sessions[0] if sessions else None


def _get_human_entity(world: World) -> int:
    humans = list(world.get_component(HumanAgent))
    assert humans
    return humans[0][0]


def _get_enemy_entity(world: World) -> int:
    enemies = list(world.get_component(RuleBasedAgent))
    assert enemies
    return enemies[0][0]


def test_dialogue_system_advances_and_completes() -> None:
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    DialogueSystem(world, bus)

    player_entity = _get_human_entity(world)
    enemy_entity = _get_enemy_entity(world)

    bus.emit(
        EVENT_DIALOGUE_START,
        left_entity=player_entity,
        right_entity=enemy_entity,
        lines=(
            {"speaker": player_entity, "text": "Hello there."},
            {"speaker": enemy_entity, "text": "General."},
        ),
        resume_mode=GameMode.COMBAT,
    )

    state = _get_state(world)
    assert state.mode == GameMode.DIALOGUE

    completed = {"fired": False}

    def _on_completed(sender, **payload):
        completed["fired"] = True

    bus.subscribe(EVENT_DIALOGUE_COMPLETED, _on_completed)

    # First click advances to the second line.
    bus.emit(EVENT_MOUSE_PRESS, x=0, y=0, button=1)
    session_entry = _get_dialogue_session(world)
    assert session_entry is not None
    session_entity, session = session_entry
    assert session.current_index == 1

    # Second click finishes the dialogue.
    bus.emit(EVENT_MOUSE_PRESS, x=0, y=0, button=1)
    assert completed["fired"] is True
    state = _get_state(world)
    assert state.mode == GameMode.COMBAT


def test_dialogue_system_default_lines() -> None:
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    DialogueSystem(world, bus)
    player_entity = _get_human_entity(world)
    enemy_entity = _get_enemy_entity(world)

    bus.emit(
        EVENT_DIALOGUE_START,
        left_entity=player_entity,
        right_entity=enemy_entity,
    )

    session_entry = _get_dialogue_session(world)
    assert session_entry is not None
    _, session = session_entry
    assert len(session.lines) >= 2
    assert session.current_line is not None
