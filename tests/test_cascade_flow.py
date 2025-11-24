from ecs.events.bus import (EventBus, EVENT_TILE_SWAP_REQUEST, EVENT_TICK,
                            EVENT_CASCADE_STEP, EVENT_CASCADE_COMPLETE, EVENT_REFILL_COMPLETED, EVENT_ANIMATION_COMPLETE)
from world import create_world
from ecs.systems.board import BoardSystem
from ecs.systems.render import RenderSystem
from ecs.systems.animation import AnimationSystem
from ecs.systems.match import MatchSystem
from ecs.systems.match_resolution import MatchResolutionSystem
from ecs.systems.turn_system import TurnSystem
from ecs.components.tile import TileType
from ecs.components.active_switch import ActiveSwitch

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
    TurnSystem(world, bus)
    mr=MatchResolutionSystem(world,bus)
    base_types = ['hex', 'nature', 'blood', 'shapeshift', 'spirit', 'secrets', 'witchfire']
    for r in range(5):
        for c in range(5):
            ent = board._get_entity_at(r, c)
            assert ent is not None, f"Missing entity at {(r,c)}"
            world.component_for_entity(ent, TileType).type_name = base_types[(r * 5 + c) % len(base_types)]
            world.component_for_entity(ent, ActiveSwitch).active = True
    # Construct board so first swap creates one match, refill yields a second match.
    # Simplify: force a horizontal near bottom and ensure above refill will line up.
    # First cascade target: row2 cols0-2 after swapping (2,2),(2,3)
    e20=board._get_entity_at(2,0); e21=board._get_entity_at(2,1); e22=board._get_entity_at(2,2); e23=board._get_entity_at(2,3)
    assert e20 and e21 and e22 and e23, 'Entities missing for initial pattern'
    # Assign matching type names alongside colors for new type-based match detection
    world.component_for_entity(e20, TileType).type_name='hex'
    world.component_for_entity(e21, TileType).type_name='hex'
    world.component_for_entity(e22, TileType).type_name='nature'
    world.component_for_entity(e23, TileType).type_name='hex'
    for ent in (e20,e21,e22,e23):
        world.component_for_entity(ent, ActiveSwitch).active = True
    # Clear a vertical slice to force refill-controlled cascade: empty cells at top of columns 1-3
    e00=board._get_entity_at(0,1); e01=board._get_entity_at(0,2); e02=board._get_entity_at(0,3)
    assert e00 and e01 and e02, 'Entities missing for cleared slice'
    world.component_for_entity(e00, ActiveSwitch).active=False
    world.component_for_entity(e01, ActiveSwitch).active=False
    world.component_for_entity(e02, ActiveSwitch).active=False
    # Deterministic second cascade: after first refill completes, force a new horizontal triple on bottom row.
    # Subscribe to cascade events
    steps=[]; complete={}
    bus.subscribe(EVENT_CASCADE_STEP, lambda s, **k: steps.append(k.get('depth')))
    bus.subscribe(EVENT_CASCADE_COMPLETE, lambda s, **k: complete.update(k))
    bus.emit(EVENT_TILE_SWAP_REQUEST, src=(2,2), dst=(2,3))
    # Run long enough for two cascades (fade 0.2 + gravity 0.25 + refill 0.25 * 2)
    forced_second = {'done': False}
    def on_refill_anim_complete(sender, **k):
        if k.get('kind') != 'refill':
            return
        if forced_second['done']:
            return
        if not steps:
            return
        e0=board._get_entity_at(0,0); e1=board._get_entity_at(0,1); e2=board._get_entity_at(0,2)
        for e in (e0,e1,e2):
            assert e is not None
            world.component_for_entity(e, TileType).type_name = 'blood'
            world.component_for_entity(e, ActiveSwitch).active = True
        forced_second['done'] = True
    bus.subscribe(EVENT_ANIMATION_COMPLETE, on_refill_anim_complete)
    drive(bus, 250)
    assert steps and max(steps) >=2, f"Cascade depth steps observed: {steps}"
    depth_val = complete.get('depth')
    assert depth_val is not None and depth_val >= 2, f"Cascade complete depth: {depth_val}"
