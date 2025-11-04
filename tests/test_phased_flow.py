from ecs.events.bus import (EventBus, EVENT_TILE_SWAP_REQUEST, EVENT_TICK,
                            EVENT_MATCH_CLEAR_BEGIN, EVENT_MATCH_FADE_COMPLETE,
                            EVENT_GRAVITY_MOVES, EVENT_REFILL_COMPLETED)
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

def test_phased_clear_gravity_refill_sequence():
    bus = EventBus()
    world = create_world(bus)
    window = DummyWindow()
    board = BoardSystem(world, bus, 5, 5)
    MatchSystem(world, bus)
    RenderSystem(world, bus, window)
    MatchResolutionSystem(world, bus, rows=5, cols=5)
    # horizontal match after swap at row 2 between (2,2) and (2,3)
    e20 = board._get_entity_at(2,0)
    e21 = board._get_entity_at(2,1)
    e22 = board._get_entity_at(2,2)
    e23 = board._get_entity_at(2,3)
    from_color = (40,40,40)
    world.component_for_entity(e20, TileColor).color = from_color
    world.component_for_entity(e21, TileColor).color = from_color
    world.component_for_entity(e22, TileColor).color = (60,60,60)
    world.component_for_entity(e23, TileColor).color = from_color

    events_order = []
    bus.subscribe(EVENT_MATCH_CLEAR_BEGIN, lambda s, **k: events_order.append('clear_begin'))
    bus.subscribe(EVENT_MATCH_FADE_COMPLETE, lambda s, **k: events_order.append('fade_complete'))
    bus.subscribe(EVENT_GRAVITY_MOVES, lambda s, **k: events_order.append('gravity_moves'))
    bus.subscribe(EVENT_REFILL_COMPLETED, lambda s, **k: events_order.append('refill_completed'))

    bus.emit(EVENT_TILE_SWAP_REQUEST, src=(2,2), dst=(2,3))
    # Fade duration 0.2s, fall duration 0.25s; tick at 0.02 -> enough ticks
    drive_ticks(bus, 80)

    assert 'clear_begin' in events_order, 'Clear begin not emitted'
    assert 'fade_complete' in events_order, 'Fade complete not emitted'
    # gravity_moves may be absent if no vertical movement occurs; ensure refill after fade at least
    assert 'refill_completed' in events_order, 'Refill not completed'
    # Sequence ordering basic check
    clear_idx = events_order.index('clear_begin')
    fade_idx = events_order.index('fade_complete')
    refill_idx = events_order.index('refill_completed')
    assert clear_idx < fade_idx < refill_idx, 'Event order incorrect'