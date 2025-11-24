import random

from ecs.events.bus import EventBus
from world import create_world
from ecs.systems.board import BoardSystem
from ecs.systems.board_ops import refill_inactive_tiles, set_spawnable_tile_types
from ecs.components.active_switch import ActiveSwitch
from ecs.components.board_position import BoardPosition
from ecs.components.tile import TileType


def _active_types(world) -> set[str]:
    types: set[str] = set()
    for entity, position in world.get_component(BoardPosition):
        try:
            switch: ActiveSwitch = world.component_for_entity(entity, ActiveSwitch)
            if not switch.active:
                continue
            tile: TileType = world.component_for_entity(entity, TileType)
        except KeyError:
            continue
        types.add(tile.type_name)
    return types


def test_board_initialization_respects_spawnable_subset():
    random.seed(0)
    bus = EventBus()
    world = create_world(bus)
    set_spawnable_tile_types(world, ["nature", "blood"])

    BoardSystem(world, bus, rows=5, cols=5)

    active_types = _active_types(world)
    assert active_types <= {"nature", "blood"}
    assert active_types, "expected board to contain at least one active tile"


def test_refill_honors_updated_spawnable_list():
    random.seed(1)
    bus = EventBus()
    world = create_world(bus)
    set_spawnable_tile_types(world, ["nature", "blood"])
    BoardSystem(world, bus, rows=3, cols=3)

    # Deactivate a tile to trigger refill.
    any_entity = next(iter(world.get_component(BoardPosition)))[0]
    switch: ActiveSwitch = world.component_for_entity(any_entity, ActiveSwitch)
    switch.active = False

    # Restrict spawnable tiles to a single option and refill.
    set_spawnable_tile_types(world, ["secrets"])
    random.seed(2)
    refill_inactive_tiles(world)

    tile: TileType = world.component_for_entity(any_entity, TileType)
    assert tile.type_name == "secrets"
    assert _active_types(world) <= {"secrets", "nature", "blood"}
