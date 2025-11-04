from ecs.events.bus import EventBus, EVENT_REFILL_COMPLETED, EVENT_TICK
from ecs.systems.board import BoardSystem
from ecs.systems.render import RenderSystem
from ecs.world import create_world
from ecs.components.tile import TileColor

class DummyWindow:
    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height

def drive(bus, ticks, dt=0.02):
    for _ in range(ticks):
        bus.emit('tick', dt=dt)

def test_refill_animation_progresses():
    bus = EventBus()
    world = create_world(bus)
    window = DummyWindow()
    board = BoardSystem(world, bus, 4, 4)
    render = RenderSystem(world, bus, window)
    # Simulate a refill event with two new tiles positions without any fade list
    new_positions = [(3,0), (3,1)]  # top row indexes (row 3 if 0 bottom)
    bus.emit(EVENT_REFILL_COMPLETED, new_tiles=new_positions)
    # Ensure spawn list populated
    assert render.refill_spawn, 'Refill spawn not initialized'
    # Drive half duration
    drive(bus, 5)  # 5*0.02 =0.1s
    mid_progress = [r['linear'] for r in render.refill_spawn]
    assert all(p > 0 for p in mid_progress), 'Progress did not advance'
    # Drive until completion
    drive(bus, 20)
    assert not render.refill_spawn, 'Refill spawn should be empty after completion'
