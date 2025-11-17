import pytest

from ecs.events.bus import (
    EventBus,
    EVENT_TICK,
    EVENT_TILE_SWAP_DO,
    EVENT_MATCH_CLEARED,
    EVENT_TURN_ADVANCED,
    EVENT_EXTRA_TURN_GRANTED,
)
from ecs.systems.board import BoardSystem
from ecs.systems.match import MatchSystem
from ecs.systems.animation import AnimationSystem
from ecs.systems.render import RenderSystem
from ecs.systems.match_resolution import MatchResolutionSystem
from ecs.systems.turn_system import TurnSystem
from ecs.systems.turn_state_utils import get_or_create_turn_state
from ecs.systems.board_ops import find_all_matches
from ecs.components.board import Board
from ecs.components.board_position import BoardPosition
from ecs.components.tile import TileType
from ecs.components.tile_types import TileTypes
from ecs.components.turn_order import TurnOrder
from ecs.components.active_turn import ActiveTurn
from ecs.components.human_agent import HumanAgent
from ecs.world import create_world


class DummyWindow:
    def __init__(self, width: int = 800, height: int = 600) -> None:
        self.width = width
        self.height = height


def _setup_world(rows: int = 5, cols: int = 5):
    bus = EventBus()
    world = create_world(bus)
    window = DummyWindow()
    board_system = BoardSystem(world, bus, rows, cols)
    MatchSystem(world, bus)
    AnimationSystem(world, bus)
    RenderSystem(world, bus, window)
    MatchResolutionSystem(world, bus)
    turn_system = TurnSystem(world, bus)
    return world, bus, board_system, turn_system


def _tile_types(world):
    entries = list(world.get_component(TileTypes))
    assert entries, "TileTypes component missing"
    return entries[0][1].all_types()


def _prepare_vertical_four_match(world, board_system, match_type: str, blocker_type: str) -> None:
    board: Board = world.component_for_entity(board_system.board_entity, Board)
    type_names = _tile_types(world)
    total_types = len(type_names)
    for row in range(board.rows):
        for col in range(board.cols):
            ent = board_system._get_entity_at(row, col)
            tile = world.component_for_entity(ent, TileType)
            tile.type_name = type_names[(row + col) % total_types]
    coords = {
        (0, 2): match_type,
        (1, 2): match_type,
        (2, 2): blocker_type,
        (3, 2): match_type,
        (2, 1): match_type,
    }
    for (row, col), type_name in coords.items():
        ent = board_system._get_entity_at(row, col)
        tile = world.component_for_entity(ent, TileType)
        tile.type_name = type_name


def _drive_until_cascade_complete(bus: EventBus, world, *, max_steps: int = 240) -> None:
    state = get_or_create_turn_state(world)
    for _ in range(max_steps):
        bus.emit(EVENT_TICK, dt=0.05)
        if not state.cascade_active and state.action_source is None and not state.cascade_observed:
            return
    pytest.fail("cascade did not settle within expected steps")


def _active_owner(world) -> int:
    entries = list(world.get_component(ActiveTurn))
    assert entries, "ActiveTurn component missing"
    return entries[0][1].owner_entity


def _owner_entities(world):
    order_entries = list(world.get_component(TurnOrder))
    assert order_entries, "TurnOrder missing"
    return order_entries[0][1].owners


def _human_entity(world):
    for entity, _ in world.get_component(HumanAgent):
        return entity
    raise AssertionError("HumanAgent not found")


def _enemy_entity(world, human_entity: int) -> int:
    for entity in _owner_entities(world):
        if entity != human_entity:
            return entity
    raise AssertionError("Enemy entity not found")


def test_player_large_match_grants_extra_turn():
    world, bus, board_system, turn_system = _setup_world()
    type_names = _tile_types(world)
    match_type = type_names[0]
    blocker_type = type_names[1]
    _prepare_vertical_four_match(world, board_system, match_type, blocker_type)
    assert not find_all_matches(world)
    initial_owner = _active_owner(world)
    turn_advanced_events = []
    extra_turn_events = []
    bus.subscribe(EVENT_TURN_ADVANCED, lambda sender, **payload: turn_advanced_events.append(payload))
    bus.subscribe(EVENT_EXTRA_TURN_GRANTED, lambda sender, **payload: extra_turn_events.append(payload))
    bus.emit(EVENT_TILE_SWAP_DO, src=(2, 1), dst=(2, 2))
    _drive_until_cascade_complete(bus, world)
    assert _active_owner(world) == initial_owner, "active turn should not advance after bonus turn"
    assert not turn_advanced_events, "bonus turn should suppress turn advancement"
    assert extra_turn_events and extra_turn_events[0]["owner_entity"] == initial_owner
    state = get_or_create_turn_state(world)
    assert state.extra_turn_pending is False
    assert turn_system.rotation_pending is False


def test_enemy_large_match_grants_extra_turn():
    world, bus, board_system, turn_system = _setup_world()
    type_names = _tile_types(world)
    match_type = type_names[0]
    blocker_type = type_names[1]
    _prepare_vertical_four_match(world, board_system, match_type, blocker_type)
    assert not find_all_matches(world)
    human = _human_entity(world)
    enemy = _enemy_entity(world, human)
    active_entries = list(world.get_component(ActiveTurn))
    assert active_entries
    active_entries[0][1].owner_entity = enemy
    order_entries = list(world.get_component(TurnOrder))
    order_comp = order_entries[0][1]
    assert enemy in order_comp.owners
    order_comp.index = order_comp.owners.index(enemy)
    turn_advanced_events = []
    extra_turn_events = []
    bus.subscribe(EVENT_TURN_ADVANCED, lambda sender, **payload: turn_advanced_events.append(payload))
    bus.subscribe(EVENT_EXTRA_TURN_GRANTED, lambda sender, **payload: extra_turn_events.append(payload))
    bus.emit(EVENT_TILE_SWAP_DO, src=(2, 1), dst=(2, 2))
    _drive_until_cascade_complete(bus, world)
    assert not turn_advanced_events, "enemy bonus turn should avoid rotation"
    assert extra_turn_events and extra_turn_events[0]["owner_entity"] == enemy
    assert _active_owner(world) == enemy
    state = get_or_create_turn_state(world)
    assert state.extra_turn_pending is False
    assert turn_system.rotation_pending is False


def test_l_shape_does_not_grant_extra_turn():
    world, bus, board_system, turn_system = _setup_world()
    # Instantiate another resolver to access helper directly without running full cascade.
    extra_resolver = MatchResolutionSystem(world, bus)
    state = get_or_create_turn_state(world)
    state.extra_turn_pending = False
    state.action_source = "swap"
    l_shape = [[(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)]]
    extra_resolver._flag_extra_turn(l_shape)
    assert state.extra_turn_pending is False


def test_t_shape_with_line_grants_extra_turn():
    world, bus, board_system, turn_system = _setup_world()
    extra_resolver = MatchResolutionSystem(world, bus)
    state = get_or_create_turn_state(world)
    state.extra_turn_pending = False
    state.action_source = "swap"
    t_shape = [[(0, 0), (0, 1), (0, 2), (0, 3), (1, 1), (2, 1)]]
    extra_resolver._flag_extra_turn(t_shape)
    assert state.extra_turn_pending is True
