from math import ceil

from ecs.events.bus import EventBus, EVENT_TILE_SWAP_REQUEST, EVENT_TILE_SWAP_DO, EVENT_TILE_SWAP_FINALIZE, EVENT_TICK
from ecs.systems.board import BoardSystem
from ecs.systems.render import RenderSystem
from ecs.systems.match import MatchSystem
from ecs.systems.animation import AnimationSystem
from ecs.components.animation_swap import SwapAnimation
from world import create_world
from ecs.components.duration import Duration
from ecs.components.tile import TileType
from ecs.components.active_switch import ActiveSwitch

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
    base_types = ['hex', 'nature', 'blood', 'shapeshift', 'spirit', 'secrets', 'witchfire']
    for r in range(3):
        for c in range(3):
            ent = board._get_entity_at(r, c)
            assert ent is not None
            world.component_for_entity(ent, TileType).type_name = base_types[(r * 3 + c) % len(base_types)]
            world.component_for_entity(ent, ActiveSwitch).active = True
    e00 = board._get_entity_at(0,0)
    e01 = board._get_entity_at(0,1)
    e02 = board._get_entity_at(0,2)
    assert e00 is not None and e01 is not None and e02 is not None
    # Assign three distinct types to ensure swap yields no match
    world.component_for_entity(e00, TileType).type_name = 'hex'
    world.component_for_entity(e01, TileType).type_name = 'nature'
    world.component_for_entity(e02, TileType).type_name = 'blood'
    world.component_for_entity(e00, ActiveSwitch).active = True
    world.component_for_entity(e01, ActiveSwitch).active = True
    world.component_for_entity(e02, ActiveSwitch).active = True
    bus.emit(EVENT_TILE_SWAP_REQUEST, src=(0,0), dst=(0,1))
    duration_value = 0.0
    for ent, _ in world.get_component(SwapAnimation):
        duration_value = world.component_for_entity(ent, Duration).value
        break
    assert duration_value > 0.0
    total_steps = ceil(((duration_value * 2) + 0.1) / 0.02)
    drive_ticks(bus, count=total_steps)
    # Swap animation should have finished (animations component inactive)
    swaps = list(world.get_component(SwapAnimation))
    assert not swaps, f'Swap animation did not finish; remaining components={len(swaps)}'
    # Colors unchanged (no DO event fired)
    assert world.component_for_entity(e00, TileType).type_name == 'hex'
    assert world.component_for_entity(e01, TileType).type_name == 'nature'

def test_valid_swap_applies():
    bus = EventBus()
    world = create_world(bus)
    window = DummyWindow()
    board = BoardSystem(world, bus, 3, 3)
    MatchSystem(world, bus)
    AnimationSystem(world, bus)
    render = RenderSystem(world, bus, window)
    base_types = ['hex', 'nature', 'blood', 'shapeshift', 'spirit', 'secrets', 'witchfire']
    for r in range(3):
        for c in range(3):
            ent = board._get_entity_at(r, c)
            assert ent is not None
            world.component_for_entity(ent, TileType).type_name = base_types[(r * 3 + c) % len(base_types)]
            world.component_for_entity(ent, ActiveSwitch).active = True
    # Pre-create a triple row so any adjacent swap there is valid
    e00 = board._get_entity_at(0,0)
    e01 = board._get_entity_at(0,1)
    e02 = board._get_entity_at(0,2)
    assert e00 is not None and e01 is not None and e02 is not None
    world.component_for_entity(e00, TileType).type_name = 'hex'
    world.component_for_entity(e01, TileType).type_name = 'hex'
    world.component_for_entity(e02, TileType).type_name = 'hex'
    world.component_for_entity(e00, ActiveSwitch).active = True
    world.component_for_entity(e01, ActiveSwitch).active = True
    world.component_for_entity(e02, ActiveSwitch).active = True
    bus.emit(EVENT_TILE_SWAP_REQUEST, src=(0,0), dst=(0,1))
    duration_value = 0.0
    for ent, _ in world.get_component(SwapAnimation):
        duration_value = world.component_for_entity(ent, Duration).value
        break
    assert duration_value > 0.0
    total_steps = ceil((duration_value + 0.1) / 0.02)
    drive_ticks(bus, total_steps)
    # Valid swap should finish forward animation and clear active_swap
    swaps = list(world.get_component(SwapAnimation))
    assert not swaps