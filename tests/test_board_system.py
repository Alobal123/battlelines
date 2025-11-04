from ecs.systems.board import BoardSystem
from ecs.events.bus import EventBus
from ecs.world import create_world

def test_is_adjacent():
    bus = EventBus()
    world = create_world(bus)
    board = BoardSystem(world, bus, 8, 8)
    assert board.is_adjacent((0,0), (0,1))
    assert board.is_adjacent((0,0), (1,0))
    assert not board.is_adjacent((0,0), (1,1))
    assert not board.is_adjacent((0,0), (2,0))
