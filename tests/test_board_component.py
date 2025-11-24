from ecs.events.bus import EventBus
from world import create_world
from ecs.systems.board import BoardSystem
from ecs.components.board import Board

def test_board_component_exists():
    bus = EventBus(); world = create_world(bus)
    board_system = BoardSystem(world, bus, 6, 7)
    boards = list(world.get_component(Board))
    assert boards, 'Board component missing'
    ent, comp = boards[0]
    assert comp.rows == 6 and comp.cols == 7
