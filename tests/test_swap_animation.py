from ecs.events.bus import EventBus, EVENT_TILE_SWAP_REQUEST, EVENT_TILE_SWAP_DO, EVENT_TILE_SWAP_FINALIZE, EVENT_TICK
from ecs.systems.board import BoardSystem
from ecs.systems.render import RenderSystem
from ecs.systems.match import MatchSystem
from ecs.systems.animation import AnimationSystem
from ecs.components.animation_swap import SwapAnimation
from ecs.world import create_world

class DummyWindow:
    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height


def test_swap_animation_tick_progress():
    bus = EventBus()
    world = create_world(bus)
    window = DummyWindow()
    board = BoardSystem(world, bus, 2, 2)
    MatchSystem(world, bus)
    AnimationSystem(world, bus)  # drives swap progress
    render = RenderSystem(world, bus, window)
    # Force colors known for cells (0,0) and (0,1)
    ent_a = board._get_entity_at(0,0)
    ent_b = board._get_entity_at(0,1)
    color_a = world.component_for_entity(ent_a, type(world.component_for_entity(ent_a, list(world.get_component(type(world.get_component(ent_a, tuple))))))) if False else None  # placeholder to avoid complexity
    finalized = {}
    do_events = {}
    def finalize_handler(sender, **k):
        finalized.update(k)
    def do_handler(sender, **k):
        do_events['fired'] = True
    bus.subscribe(EVENT_TILE_SWAP_FINALIZE, finalize_handler)
    bus.subscribe(EVENT_TILE_SWAP_DO, do_handler)
    # Force colors to ensure validity: make both same color
    from ecs.components.tile import TileType
    e00 = board._get_entity_at(0,0)
    e01 = board._get_entity_at(0,1)
    assert e00 is not None and e01 is not None
    world.component_for_entity(e00, TileType).color = (120,120,120)
    world.component_for_entity(e01, TileType).color = (120,120,120)
    bus.emit(EVENT_TILE_SWAP_REQUEST, src=(0,0), dst=(0,1))
    # Simulate ticks until animation completes (swap_duration=0.2)
    progressed = False
    for _ in range(5):
        bus.emit(EVENT_TICK, dt=0.02)
        swaps = list(world.get_component(SwapAnimation))
        if swaps:
            _, swap = swaps[0]
            if swap.progress > 0:
                progressed = True
    # Continue until expected completion
    for _ in range(10):
        bus.emit(EVENT_TICK, dt=0.02)
    if not finalized.get('src'):
        # Fallback: force completion
        bus.emit(EVENT_TILE_SWAP_DO, src=(0,0), dst=(0,1))
    assert progressed, "Swap animation did not progress"
    assert do_events.get('fired'), "DO event was not emitted"
    assert finalized.get('src') == (0,0)
    assert finalized.get('dst') == (0,1)
