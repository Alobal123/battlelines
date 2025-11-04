from ecs.events.bus import (EventBus, EVENT_TILE_SWAP_REQUEST, EVENT_TICK,
                            EVENT_MATCH_FOUND, EVENT_GRAVITY_MOVES, EVENT_GRAVITY_SETTLED)
from ecs.systems.board import BoardSystem
from ecs.systems.render import RenderSystem
from ecs.systems.match import MatchSystem
from ecs.systems.match_resolution import MatchResolutionSystem
from ecs.world import create_world
from ecs.components.tile import TileColor

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
    RenderSystem(world, bus, window)
    MatchResolutionSystem(world, bus, rows=5, cols=5)
    # Create vertical match after swap at column 0 between (3,0) and (4,0)
    e00 = board._get_entity_at(0,0)
    e10 = board._get_entity_at(1,0)
    e20 = board._get_entity_at(2,0)
    e30 = board._get_entity_at(3,0)
    e40 = board._get_entity_at(4,0)
    world.component_for_entity(e00, TileColor).color = (9,9,9)
    world.component_for_entity(e10, TileColor).color = (9,9,9)
    world.component_for_entity(e20, TileColor).color = (9,9,9)
    world.component_for_entity(e30, TileColor).color = (15,15,15)
    world.component_for_entity(e40, TileColor).color = (9,9,9)

    match_found = {}
    gravity_moves = {}
    gravity_settled = {}
    bus.subscribe(EVENT_MATCH_FOUND, lambda s, **k: match_found.update(k))
    bus.subscribe(EVENT_GRAVITY_MOVES, lambda s, **k: gravity_moves.update(k))
    bus.subscribe(EVENT_GRAVITY_SETTLED, lambda s, **k: gravity_settled.update(k))

    bus.emit(EVENT_TILE_SWAP_REQUEST, src=(3,0), dst=(4,0))
    drive_ticks(bus, 40)
    assert match_found.get('positions'), 'Match not detected'
    assert gravity_moves.get('moves'), 'Gravity moves not emitted'
    # Ensure settlement occurs after falling
    drive_ticks(bus, 40)
    assert gravity_settled.get('moves') is not None, 'Gravity did not settle'