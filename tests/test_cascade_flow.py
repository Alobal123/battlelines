from ecs.events.bus import (EventBus, EVENT_TILE_SWAP_REQUEST, EVENT_TICK,
                            EVENT_CASCADE_STEP, EVENT_CASCADE_COMPLETE, EVENT_REFILL_COMPLETED)
from ecs.world import create_world
from ecs.systems.board import BoardSystem
from ecs.systems.render import RenderSystem
from ecs.systems.animation import AnimationSystem
from ecs.systems.match import MatchSystem
from ecs.systems.match_resolution import MatchResolutionSystem
from ecs.components.tile import TileType

class DummyWindow:
    def __init__(self, width=800, height=600):
        self.width=width; self.height=height

def drive(bus, ticks, dt=0.02):
    for _ in range(ticks):
        bus.emit('tick', dt=dt)

def test_two_step_cascade():
    bus=EventBus(); world=create_world(bus); window=DummyWindow()
    board=BoardSystem(world,bus,5,5)
    match=MatchSystem(world,bus)
    AnimationSystem(world,bus)
    render=RenderSystem(world,bus,window)
    mr=MatchResolutionSystem(world,bus)
    # Construct board so first swap creates one match, refill yields a second match.
    # Simplify: force a horizontal near bottom and ensure above refill will line up.
    # First cascade target: row2 cols0-2 after swapping (2,2),(2,3)
    e20=board._get_entity_at(2,0); e21=board._get_entity_at(2,1); e22=board._get_entity_at(2,2); e23=board._get_entity_at(2,3)
    assert e20 and e21 and e22 and e23, 'Entities missing for initial pattern'
    world.component_for_entity(e20, TileType).color=(50,50,50)
    world.component_for_entity(e21, TileType).color=(50,50,50)
    world.component_for_entity(e22, TileType).color=(60,60,60)
    world.component_for_entity(e23, TileType).color=(50,50,50)
    # Clear a vertical slice to force refill-controlled cascade: empty cells at top of columns 1-3
    e00=board._get_entity_at(0,1); e01=board._get_entity_at(0,2); e02=board._get_entity_at(0,3)
    assert e00 and e01 and e02, 'Entities missing for cleared slice'
    world.component_for_entity(e00, TileType).color=None
    world.component_for_entity(e01, TileType).color=None
    world.component_for_entity(e02, TileType).color=None
    # Deterministic second cascade: after first refill completes, force a new horizontal triple on bottom row.
    # Subscribe to cascade events
    steps=[]; complete={}
    bus.subscribe(EVENT_CASCADE_STEP, lambda s, **k: steps.append(k.get('depth')))
    bus.subscribe(EVENT_CASCADE_COMPLETE, lambda s, **k: complete.update(k))
    bus.emit(EVENT_TILE_SWAP_REQUEST, src=(2,2), dst=(2,3))
    # Run long enough for two cascades (fade 0.2 + gravity 0.25 + refill 0.25 * 2)
    forced_second = {'done': False}
    def on_refill(sender, **k):
        # Only apply once after first cascade step
        if forced_second['done']:
            return
        # Ensure first cascade step occurred
        if not steps:
            return
        # Force row 0 cols 0-2 to same color
        e0=board._get_entity_at(0,0); e1=board._get_entity_at(0,1); e2=board._get_entity_at(0,2)
        for e in (e0,e1,e2):
            assert e is not None
            tc = world.component_for_entity(e, TileType)
            tc.color = (90,90,90)
        forced_second['done'] = True
    bus.subscribe(EVENT_REFILL_COMPLETED, on_refill)
    drive(bus, 250)
    assert steps and max(steps) >=2, f"Cascade depth steps observed: {steps}"
    depth_val = complete.get('depth')
    assert depth_val is not None and depth_val >= 2, f"Cascade complete depth: {depth_val}"
