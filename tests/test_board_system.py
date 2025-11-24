from ecs.systems.board import BoardSystem
from ecs.events.bus import (
    EventBus,
    EVENT_TILE_CLICK,
    EVENT_TILE_SELECTED,
    EVENT_ABILITY_TARGET_MODE,
    EVENT_ABILITY_TARGET_SELECTED,
)
from world import create_world

def test_is_adjacent():
    bus = EventBus()
    world = create_world(bus)
    board = BoardSystem(world, bus, 8, 8)
    assert board.is_adjacent((0,0), (0,1))
    assert board.is_adjacent((0,0), (1,0))
    assert not board.is_adjacent((0,0), (1,1))
    assert not board.is_adjacent((0,0), (2,0))


def test_tile_clicks_ignored_while_ability_targeting_active():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    BoardSystem(world, bus, rows=2, cols=2)

    selections: list[tuple[int, int]] = []
    bus.subscribe(
        EVENT_TILE_SELECTED,
        lambda sender, **payload: selections.append((payload["row"], payload["col"])),
    )

    # Enter targeting mode and ensure normal tile clicks are ignored.
    bus.emit(EVENT_ABILITY_TARGET_MODE, ability_entity=1, owner_entity=None)
    bus.emit(EVENT_TILE_CLICK, row=0, col=0)
    assert selections == []

    # Once targeting resolves, tile clicks should resume normal behavior.
    bus.emit(EVENT_ABILITY_TARGET_SELECTED, ability_entity=1, target=(0, 0))
    bus.emit(EVENT_TILE_CLICK, row=1, col=0)
    assert selections == [(1, 0)]
