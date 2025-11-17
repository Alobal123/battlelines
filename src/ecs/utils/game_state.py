from __future__ import annotations

from esper import World

from ecs.components.game_state import GameMode, GameState
from ecs.events.bus import EVENT_GAME_MODE_CHANGED, EventBus


def set_game_mode(world: World, event_bus: EventBus, mode: GameMode) -> None:
    """Update the global game mode and emit a change event when it differs."""

    previous_mode = None
    for _, state in world.get_component(GameState):
        previous_mode = state.mode
        if state.mode == mode:
            return
        state.mode = mode
        event_bus.emit(
            EVENT_GAME_MODE_CHANGED,
            previous_mode=previous_mode,
            new_mode=mode,
        )
        return
    # No existing GameState component; create a new one.
    state_entity = world.create_entity()
    world.add_component(state_entity, GameState(mode=mode))
    event_bus.emit(
        EVENT_GAME_MODE_CHANGED,
        previous_mode=previous_mode,
        new_mode=mode,
    )
