from ecs.events.bus import (EventBus, EVENT_TILE_SWAP_REQUEST, EVENT_TICK,
                            EVENT_MATCH_FOUND, EVENT_MATCH_CLEARED, EVENT_GRAVITY_APPLIED, EVENT_REFILL_COMPLETED)
from ecs.systems.board import BoardSystem
from ecs.systems.render import RenderSystem
from ecs.systems.animation import AnimationSystem
from ecs.systems.match import MatchSystem
from ecs.systems.match_resolution import MatchResolutionSystem
from ecs.systems.turn_system import TurnSystem
from ecs.world import create_world
from ecs.components.tile import TileType
from ecs.components.active_switch import ActiveSwitch

class DummyWindow:
    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height

def drive_ticks(bus, count=30, dt=0.02):
    for _ in range(count):
        bus.emit(EVENT_TICK, dt=dt)

def test_horizontal_match_clears_and_refills():
    bus = EventBus()
    world = create_world(bus)
    window = DummyWindow()
    board = BoardSystem(world, bus, 5, 5)
    MatchSystem(world, bus)
    AnimationSystem(world, bus)
    RenderSystem(world, bus, window)
    TurnSystem(world, bus)
    MatchResolutionSystem(world, bus)
    # Force a horizontal triple at row 2 columns 0-2 after swap between (2,2) and (2,3)
    e20 = board._get_entity_at(2,0)
    e21 = board._get_entity_at(2,1)
    e22 = board._get_entity_at(2,2)
    e23 = board._get_entity_at(2,3)
    assert e20 and e21 and e22 and e23
    # Set types/colors so that swapping e22,e23 makes columns 0-2 same type
    t0 = world.component_for_entity(e20, TileType)
    t1 = world.component_for_entity(e21, TileType)
    t2 = world.component_for_entity(e22, TileType)
    t3 = world.component_for_entity(e23, TileType)
    # Use distinct placeholder palette colors but enforce type consistency for match detection
    t0.type_name = 'ranged'
    t1.type_name = 'ranged'
    t2.type_name = 'cavalry'
    t3.type_name = 'ranged'
    for ent in (e20,e21,e22,e23):
        world.component_for_entity(ent, ActiveSwitch).active = True

    found = {}
    cleared = {}
    gravity = {}
    refill = {}
    bus.subscribe(EVENT_MATCH_FOUND, lambda s, **k: found.update(k))
    bus.subscribe(EVENT_MATCH_CLEARED, lambda s, **k: cleared.update(k))
    bus.subscribe(EVENT_GRAVITY_APPLIED, lambda s, **k: gravity.update(k))
    bus.subscribe(EVENT_REFILL_COMPLETED, lambda s, **k: refill.update(k))

    bus.emit(EVENT_TILE_SWAP_REQUEST, src=(2,2), dst=(2,3))
    # Drive ticks until cleared emitted or timeout
    for _ in range(180):  # allow fade + gravity + refill (~3.6s simulated max)
        if not cleared.get('positions') or not refill.get('new_tiles'):
            bus.emit(EVENT_TICK, dt=0.02)
        if cleared.get('positions') and refill.get('new_tiles'):
            break
    assert found.get('positions'), 'Match not detected'
    assert cleared.get('positions') == found.get('positions'), 'Cleared positions differ'
    # Gravity should have run (even if no vertical movement it counts cascade if empties existed)
    assert 'cascades' in gravity
    assert refill.get('new_tiles'), 'No refill occurred'
    # Ensure cleared positions now active again after refill
    found_positions = found.get('positions') or []
    for (r,c) in found_positions:
        ent = board._get_entity_at(r,c)
        assert ent is not None
        active_sw = world.component_for_entity(ent, ActiveSwitch)
        assert active_sw.active