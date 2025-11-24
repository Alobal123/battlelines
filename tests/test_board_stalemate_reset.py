import random

from ecs.events.bus import (
    EVENT_BOARD_CHANGED,
    EVENT_MATCH_FOUND,
    EVENT_REFILL_COMPLETED,
    EVENT_TICK,
    EventBus,
)
from ecs.systems.board import BoardSystem
from ecs.systems.match import MatchSystem
from ecs.systems.animation import AnimationSystem
from ecs.systems.turn_system import TurnSystem
from ecs.systems.match_resolution import MatchResolutionSystem
from ecs.systems.board_ops import find_all_matches, find_valid_swaps
from ecs.components.tile import TileType
from ecs.components.active_switch import ActiveSwitch
from world import create_world


def drive_ticks(bus: EventBus, count: int = 240, dt: float = 0.05) -> None:
    for _ in range(count):
        bus.emit(EVENT_TICK, dt=dt)


def test_stalemate_triggers_board_reset():
    bus = EventBus()
    world = create_world(bus)
    rng = getattr(world, "random", None)
    if isinstance(rng, random.Random):
        rng.seed(1234)

    board = BoardSystem(world, bus, rows=5, cols=5)
    MatchSystem(world, bus)
    AnimationSystem(world, bus)
    TurnSystem(world, bus)
    MatchResolutionSystem(world, bus)

    palette = board._registry().all_types()
    assert len(palette) >= 3, "Need at least three tile types to construct stalemate pattern"
    pattern = palette[:3]

    for row in range(5):
        for col in range(5):
            entity = board._get_entity_at(row, col)
            assert entity is not None
            tile = world.component_for_entity(entity, TileType)
            tile.type_name = pattern[(row + col) % 3]
            switch = world.component_for_entity(entity, ActiveSwitch)
            switch.active = True

    assert not find_all_matches(world), "Setup should not contain initial matches"
    assert not find_valid_swaps(world), "Pattern should eliminate all valid moves"

    match_events: list[dict] = []
    refill_events: list[dict] = []
    bus.subscribe(EVENT_MATCH_FOUND, lambda sender, **payload: match_events.append(payload))
    bus.subscribe(EVENT_REFILL_COMPLETED, lambda sender, **payload: refill_events.append(payload))

    bus.emit(EVENT_BOARD_CHANGED, reason="test_stalemate")
    drive_ticks(bus)

    assert match_events, "Expected a match-like event for stalemate reset"
    assert any(evt.get("reason") == "stalemate_reset" for evt in match_events)

    assert refill_events, "Board should refill after reset"
    new_tiles = refill_events[-1].get("new_tiles", [])
    assert len(new_tiles) == 25, "All tiles should be respawned"

    drive_ticks(bus, count=60)

    assert not find_all_matches(world), "New board should start without matches"
    assert find_valid_swaps(world), "New board should provide at least one valid move"
