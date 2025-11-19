from __future__ import annotations

from esper import World

from ecs.components.game_state import GameMode, GameState
from ecs.events.bus import EVENT_GAME_MODE_CHANGED, EventBus


def _sanitize_press_id(value: int | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def set_game_mode(
    world: World,
    event_bus: EventBus,
    mode: GameMode,
    *,
    input_guard_press_id: int | None = None,
) -> None:
    """Update the global game mode and emit a change event when it differs."""

    guard_id = _sanitize_press_id(input_guard_press_id)
    previous_mode: GameMode | None = None
    for _, state in world.get_component(GameState):
        previous_mode = state.mode
        changed = state.mode != mode
        if changed:
            state.mode = mode
        if changed or guard_id is not None:
            state.input_guard_press_id = guard_id
            event_bus.emit(
                EVENT_GAME_MODE_CHANGED,
                previous_mode=previous_mode,
                new_mode=mode,
                input_guard_press_id=guard_id,
            )
        return
    # No existing GameState component; create a new one.
    state_entity = world.create_entity()
    state = GameState(mode=mode, input_guard_press_id=guard_id)
    world.add_component(state_entity, state)
    event_bus.emit(
        EVENT_GAME_MODE_CHANGED,
        previous_mode=previous_mode,
        new_mode=mode,
        input_guard_press_id=guard_id,
    )
