from ecs.events.bus import EventBus, EVENT_TILE_SWAP_REQUEST, EVENT_TILE_SWAP_DO, EVENT_TILE_SWAP_FINALIZE, EVENT_TICK
from ecs.systems.board import BoardSystem
from ecs.systems.render import RenderSystem
from ecs.systems.match import MatchSystem
from ecs.systems.animation import AnimationSystem
from ecs.components.animation_swap import SwapAnimation
from ecs.world import create_world
from ecs.components.tile import TileType

class DummyWindow:
    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height

def drive_ticks(bus, count=30, dt=0.02):
    for _ in range(count):
        bus.emit(EVENT_TICK, dt=dt)

def test_invalid_swap_reverts():
    bus = EventBus()
    world = create_world(bus)
    window = DummyWindow()
    board = BoardSystem(world, bus, 3, 3)
    MatchSystem(world, bus)
    AnimationSystem(world, bus)
    render = RenderSystem(world, bus, window)
    e00 = board._get_entity_at(0,0)
    e01 = board._get_entity_at(0,1)
    e02 = board._get_entity_at(0,2)
    assert e00 is not None and e01 is not None and e02 is not None
    world.component_for_entity(e00, TileType).color = (10,10,10)
    world.component_for_entity(e01, TileType).color = (20,20,20)
    world.component_for_entity(e02, TileType).color = (30,30,30)
    bus.emit(EVENT_TILE_SWAP_REQUEST, src=(0,0), dst=(0,1))
    # animate forward+reverse
    # Initial forward phase (0.2s) then reverse (0.2s). Provide enough ticks for both (~20 total).
    drive_ticks(bus, count=25)
    # Swap animation should have finished (animations component inactive)
    swaps = list(world.get_component(SwapAnimation))
    assert not swaps, f'Swap animation did not finish; remaining components={len(swaps)}'
    # Colors unchanged (no DO event fired)
    assert world.component_for_entity(e00, TileType).color == (10,10,10)
    assert world.component_for_entity(e01, TileType).color == (20,20,20)

def test_valid_swap_applies():
    bus = EventBus()
    world = create_world(bus)
    window = DummyWindow()
    board = BoardSystem(world, bus, 3, 3)
    MatchSystem(world, bus)
    AnimationSystem(world, bus)
    render = RenderSystem(world, bus, window)
    # Pre-create a triple row so any adjacent swap there is valid
    e00 = board._get_entity_at(0,0)
    e01 = board._get_entity_at(0,1)
    e02 = board._get_entity_at(0,2)
    assert e00 is not None and e01 is not None and e02 is not None
    world.component_for_entity(e00, TileType).color = (50,50,50)
    world.component_for_entity(e01, TileType).color = (50,50,50)
    world.component_for_entity(e02, TileType).color = (50,50,50)
    bus.emit(EVENT_TILE_SWAP_REQUEST, src=(0,0), dst=(0,1))
    drive_ticks(bus, 15)
    # Valid swap should finish forward animation and clear active_swap
    swaps = list(world.get_component(SwapAnimation))
    assert not swaps