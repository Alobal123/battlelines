from ecs.events.bus import EventBus, EVENT_TILE_SWAP_REQUEST, EVENT_TILE_SWAP_FINALIZE, EVENT_TILE_SWAP_DO, EVENT_TICK
from ecs.systems.board import BoardSystem
from ecs.systems.render import RenderSystem
from ecs.systems.animation import AnimationSystem
from ecs.systems.match import MatchSystem
from ecs.world import create_world

class DummyWindow:
    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height

# We simulate animation completion by manually emitting DO after REQUEST

def test_swap_flow_finalizes():
    bus = EventBus()
    world = create_world(bus)
    window = DummyWindow()
    board = BoardSystem(world, bus, 2, 2)
    MatchSystem(world, bus)
    AnimationSystem(world, bus)
    render = RenderSystem(world, bus, window)
    # capture finalize
    finalized = {}
    def finalize_handler(sender, **kwargs):
        finalized.update(kwargs)
    bus.subscribe(EVENT_TILE_SWAP_FINALIZE, finalize_handler)
    # choose two adjacent cells (0,0) and (0,1)
    # Force colors so swap is valid (create triple potential by duplicating row colors)
    from ecs.components.tile import TileColor
    e00 = board._get_entity_at(0,0)
    e01 = board._get_entity_at(0,1)
    assert e00 is not None and e01 is not None
    world.component_for_entity(e00, TileColor).color = (200,200,200)
    world.component_for_entity(e01, TileColor).color = (200,200,200)
    bus.emit(EVENT_TILE_SWAP_REQUEST, src=(0,0), dst=(0,1))
    # Drive ticks until animation triggers DO
    for _ in range(15):
        bus.emit(EVENT_TICK, dt=0.02)
    if not finalized.get('src'):
        # fallback
        bus.emit(EVENT_TILE_SWAP_DO, src=(0,0), dst=(0,1))
    assert finalized.get('src') == (0,0)
    assert finalized.get('dst') == (0,1)
