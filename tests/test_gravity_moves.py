from ecs.events.bus import (EventBus, EVENT_TILE_SWAP_REQUEST, EVENT_TICK,
                            EVENT_MATCH_FOUND, EVENT_ANIMATION_START, EVENT_ANIMATION_COMPLETE)
from ecs.systems.board import BoardSystem
from ecs.systems.render import RenderSystem
from ecs.systems.animation import AnimationSystem
from ecs.systems.match import MatchSystem
from ecs.systems.match_resolution import MatchResolutionSystem
from ecs.world import create_world
from ecs.components.tile import TileType
from ecs.components.active_switch import ActiveSwitch

class DummyWindow:
    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height

def drive_ticks(bus, count=60, dt=0.02):
    for _ in range(count):
        bus.emit(EVENT_TICK, dt=dt)

def test_gravity_moves_emitted():
    bus = EventBus()
    world = create_world(bus)
    window = DummyWindow()
    board = BoardSystem(world, bus, 5, 5)
    MatchSystem(world, bus)
    AnimationSystem(world, bus)
    RenderSystem(world, bus, window)
    MatchResolutionSystem(world, bus)
    # Create vertical match after swap at column 0 between (3,0) and (4,0)
    e00 = board._get_entity_at(0,0)
    e10 = board._get_entity_at(1,0)
    e20 = board._get_entity_at(2,0)
    e30 = board._get_entity_at(3,0)
    e40 = board._get_entity_at(4,0)
    assert e00 is not None
    assert e10 is not None
    assert e20 is not None
    assert e30 is not None
    assert e40 is not None
    world.component_for_entity(e00, TileType).type_name='archers'
    world.component_for_entity(e10, TileType).type_name='archers'
    world.component_for_entity(e20, TileType).type_name='archers'
    world.component_for_entity(e30, TileType).type_name='cavalry'
    world.component_for_entity(e40, TileType).type_name='archers'
    for ent in (e00,e10,e20,e30,e40):
        world.component_for_entity(ent, ActiveSwitch).active = True

    match_found = {}
    fall_start = {}
    fall_complete = {}
    bus.subscribe(EVENT_MATCH_FOUND, lambda s, **k: match_found.update(k))
    def on_anim_start(sender, **k):
        if k.get('kind') == 'fall':
            fall_start.update(k)
    def on_anim_complete(sender, **k):
        if k.get('kind') == 'fall':
            fall_complete.update(k)
    bus.subscribe(EVENT_ANIMATION_START, on_anim_start)
    bus.subscribe(EVENT_ANIMATION_COMPLETE, on_anim_complete)

    bus.emit(EVENT_TILE_SWAP_REQUEST, src=(3,0), dst=(4,0))
    drive_ticks(bus, 40)
    assert match_found.get('positions'), 'Match not detected'
    assert fall_start.get('kind') == 'fall', 'Fall animation not started'
    drive_ticks(bus, 60)
    assert fall_complete.get('kind') == 'fall', 'Fall animation not completed'