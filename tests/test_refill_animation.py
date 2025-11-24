from ecs.events.bus import EventBus, EVENT_REFILL_COMPLETED, EVENT_TICK, EVENT_ANIMATION_START
from ecs.systems.board import BoardSystem
from ecs.systems.render import RenderSystem
from ecs.systems.animation import AnimationSystem
from ecs.components.animation_refill import RefillAnimation
from world import create_world
from ecs.components.tile import TileType

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
    AnimationSystem(world, bus)
    render = RenderSystem(world, bus, window)
    # Simulate a refill event with two new tiles positions without any fade list
    new_positions = [(3,0), (3,1)]  # top row indexes (row 3 if 0 bottom)
    # Emit logical refill completion then start refill animation explicitly (mirrors MatchResolutionSystem behavior)
    bus.emit(EVENT_REFILL_COMPLETED, new_tiles=new_positions)
    bus.emit(EVENT_ANIMATION_START, kind='refill', items=new_positions)
    # Ensure spawn list populated
    refills = list(world.get_component(RefillAnimation))
    assert refills, 'Refill spawn not initialized'
    # Drive half duration
    drive(bus, 5)  # 5*0.02 =0.1s
    mid_progress = [r[1].linear for r in refills]
    assert all(p > 0 for p in mid_progress), 'Progress did not advance'
    # Drive until completion
    drive(bus, 20)
    refills = list(world.get_component(RefillAnimation))
    assert not refills, 'Refill components should be removed after completion'
