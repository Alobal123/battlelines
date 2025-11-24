import pytest
from ecs.events.bus import EventBus, EVENT_MOUSE_PRESS, EVENT_TILE_DESELECTED
from world import create_world
from ecs.systems.board import BoardSystem
from ecs.systems.render import RenderSystem
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.ability_targeting_system import AbilityTargetingSystem

@pytest.fixture
def setup_world():
    bus = EventBus()
    world = create_world(bus)
    class DummyWindow:
        width = 800
        height = 600
    window = DummyWindow()
    board = BoardSystem(world, bus)
    render = RenderSystem(world, bus, window)
    AbilityTargetingSystem(world, bus)
    ability = AbilitySystem(world, bus)
    return bus, world, board, render

def test_right_click_deselect_emits_event(setup_world):
    bus, world, board, render = setup_world
    # Manually set a selection to simulate prior left-click
    board.selected = (0,0)
    captured = {}
    def handler(sender, **payload):
        captured.update(payload)
    bus.subscribe(EVENT_TILE_DESELECTED, handler)
    # Fire right-click
    bus.emit(EVENT_MOUSE_PRESS, x=0, y=0, button=4)
    assert board.selected is None, 'Selection should be cleared on right-click'
    assert captured.get('reason') == 'right_click'
    assert captured.get('prev_row') == 0 and captured.get('prev_col') == 0

