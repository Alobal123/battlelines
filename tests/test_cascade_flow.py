from ecs.events.bus import (EventBus, EVENT_TILE_SWAP_REQUEST, EVENT_TICK,
                            EVENT_CASCADE_STEP, EVENT_CASCADE_COMPLETE, EVENT_MATCH_FOUND,
                            EVENT_MATCH_CLEAR_BEGIN, EVENT_MATCH_FADE_COMPLETE)
from ecs.world import create_world
from ecs.systems.board import BoardSystem
from ecs.systems.render import RenderSystem
from ecs.systems.match import MatchSystem
from ecs.systems.match_resolution import MatchResolutionSystem
from ecs.components.tile import TileColor

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
    render=RenderSystem(world,bus,window)
    mr=MatchResolutionSystem(world,bus,rows=5,cols=5)
    # Construct board so first swap creates one match, refill yields a second match.
    # Simplify: force a horizontal near bottom and ensure above refill will line up.
    # First cascade target: row2 cols0-2 after swapping (2,2),(2,3)
    e20=board._get_entity_at(2,0); e21=board._get_entity_at(2,1); e22=board._get_entity_at(2,2); e23=board._get_entity_at(2,3)
    world.component_for_entity(e20, TileColor).color=(50,50,50)
    world.component_for_entity(e21, TileColor).color=(50,50,50)
    world.component_for_entity(e22, TileColor).color=(60,60,60)
    world.component_for_entity(e23, TileColor).color=(50,50,50)
    # Prepare cells above (rows3,4) so after gravity/refill second horizontal forms at row1 or row0
    # Force potential second match at row0 columns 1-3 after refill by clearing colors there.
    e00=board._get_entity_at(0,1); e01=board._get_entity_at(0,2); e02=board._get_entity_at(0,3)
    world.component_for_entity(e00, TileColor).color=(80,80,80)
    world.component_for_entity(e01, TileColor).color=(80,80,80)
    world.component_for_entity(e02, TileColor).color=(80,80,80)
    # Subscribe to cascade events
    steps=[]; complete={}
    bus.subscribe(EVENT_CASCADE_STEP, lambda s, **k: steps.append(k.get('depth')))
    bus.subscribe(EVENT_CASCADE_COMPLETE, lambda s, **k: complete.update(k))
    bus.emit(EVENT_TILE_SWAP_REQUEST, src=(2,2), dst=(2,3))
    # Run long enough for two cascades (fade 0.2 + gravity 0.25 + refill 0.25 * 2)
    drive(bus, 300)
    assert steps and steps[0] == 2 or max(steps) >=2, 'Cascade step 2 not reached'
    assert complete.get('depth') >= 2, 'Cascade depth should be >=2'
