from ecs.events.bus import EventBus, EVENT_MOUSE_PRESS, EVENT_TILE_CLICK
from ecs.systems.input import InputSystem
from ecs.constants import GRID_ROWS, GRID_COLS, TILE_SIZE, BOTTOM_MARGIN

class DummyWindow:
    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height


def test_mouse_press_translates_to_tile_click():
    bus = EventBus()
    window = DummyWindow()
    input_system = InputSystem(bus, window)
    received = {}
    def handler(sender, **kwargs):
        received.update(kwargs)
    bus.subscribe(EVENT_TILE_CLICK, handler)
    pressed = {}
    def press_handler(sender, **kwargs):
        pressed.update(kwargs)
    bus.subscribe(EVENT_MOUSE_PRESS, press_handler)
    # Click inside first cell (row0,col0)
    x = (window.width - GRID_COLS * TILE_SIZE)/2 + TILE_SIZE/2 + 1
    y = BOTTOM_MARGIN + TILE_SIZE/2 + 1
    bus.emit(EVENT_MOUSE_PRESS, x=x, y=y, button=1)
    assert pressed.get('x') == x
    assert pressed.get('y') == y
    assert received.get('row') == 0
    assert received.get('col') == 0
