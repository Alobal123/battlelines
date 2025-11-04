from ecs.events.bus import (EventBus, EVENT_TILE_SWAP_REQUEST, EVENT_TICK,
                            EVENT_ANIMATION_START, EVENT_ANIMATION_COMPLETE, EVENT_REFILL_COMPLETED)
from ecs.systems.board import BoardSystem
from ecs.systems.render import RenderSystem
from ecs.systems.animation import AnimationSystem
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
    AnimationSystem(world, bus)
    RenderSystem(world, bus, window)
    MatchResolutionSystem(world, bus)
    # horizontal match after swap at row 2 between (2,2) and (2,3)
    e20 = board._get_entity_at(2,0)
    e21 = board._get_entity_at(2,1)
    e22 = board._get_entity_at(2,2)
    e23 = board._get_entity_at(2,3)
    assert e20 is not None
    assert e21 is not None
    assert e22 is not None
    assert e23 is not None
    from_color = (40,40,40)
    world.component_for_entity(e20, TileColor).color = from_color
    world.component_for_entity(e21, TileColor).color = from_color
    world.component_for_entity(e22, TileColor).color = (60,60,60)
    world.component_for_entity(e23, TileColor).color = from_color

    events_order = []
    def on_anim_start(sender, **k):
        if k.get('kind') == 'fade':
            events_order.append('clear_begin')
        if k.get('kind') == 'fall':
            events_order.append('gravity_moves')
        if k.get('kind') == 'refill':
            events_order.append('refill_started')
    def on_anim_complete(sender, **k):
        if k.get('kind') == 'fade':
            events_order.append('fade_complete')
        if k.get('kind') == 'refill':
            events_order.append('refill_completed')
    bus.subscribe(EVENT_ANIMATION_START, on_anim_start)
    bus.subscribe(EVENT_ANIMATION_COMPLETE, on_anim_complete)
    bus.subscribe(EVENT_REFILL_COMPLETED, lambda s, **k: events_order.append('refill_logic'))

    bus.emit(EVENT_TILE_SWAP_REQUEST, src=(2,2), dst=(2,3))
    # Fade duration 0.2s, fall duration 0.25s; tick at 0.02 -> enough ticks
    drive_ticks(bus, 80)

    assert 'clear_begin' in events_order, f'Fade animation not started: {events_order}'
    assert 'fade_complete' in events_order, f'Fade animation not completed: {events_order}'
    assert 'refill_completed' in events_order, f'Refill animation not completed: {events_order}'
    clear_idx = events_order.index('clear_begin')
    fade_idx = events_order.index('fade_complete')
    refill_idx = events_order.index('refill_completed')
    assert clear_idx < fade_idx < refill_idx, f'Ordering wrong: {events_order}'