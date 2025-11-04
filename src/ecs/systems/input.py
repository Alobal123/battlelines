from ecs.events.bus import EventBus, EVENT_MOUSE_PRESS, EVENT_TILE_CLICK
from ecs.constants import GRID_COLS, GRID_ROWS, TILE_SIZE, BOTTOM_MARGIN

class InputSystem:
    def __init__(self, event_bus: EventBus, window):
        self.event_bus = event_bus
        self.window = window
        self.event_bus.subscribe(EVENT_MOUSE_PRESS, self.on_mouse_press)

    def on_mouse_press(self, sender, **kwargs):
        x = kwargs.get('x')
        y = kwargs.get('y')
        if x is None or y is None:
            return
        total_width = GRID_COLS * TILE_SIZE
        start_x = (self.window.width - total_width) / 2
        start_y = BOTTOM_MARGIN
        if x < start_x or x > start_x + total_width:
            return
        if y < start_y or y > start_y + GRID_ROWS * TILE_SIZE:
            return
        col = int((x - start_x) // TILE_SIZE)
        row = int((y - start_y) // TILE_SIZE)
        if 0 <= row < GRID_ROWS and 0 <= col < GRID_COLS:
            self.event_bus.emit(EVENT_TILE_CLICK, row=row, col=col)
