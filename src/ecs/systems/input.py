from ecs.events.bus import EventBus, EVENT_MOUSE_PRESS, EVENT_TILE_CLICK, EVENT_ABILITY_ACTIVATE_REQUEST
from ecs.constants import GRID_COLS, GRID_ROWS
from ecs.ui.layout import compute_board_geometry

class InputSystem:
    def __init__(self, event_bus: EventBus, window, world=None):
        self.event_bus = event_bus
        self.window = window
        self.world = world  # optional world ref for ability activation lookup
        self.event_bus.subscribe(EVENT_MOUSE_PRESS, self.on_mouse_press)

    def on_mouse_press(self, sender, **kwargs):
        x = kwargs.get('x')
        y = kwargs.get('y')
        button = kwargs.get('button')
        if x is None or y is None:
            return
        # Left button (1) drives activation or tile clicks. Other buttons fall through (so right-click can be handled by other systems).
        if button != 1:
            return  # Do not emit tile click or ability activation for non-left buttons; Board/Ability systems listen directly to EVENT_MOUSE_PRESS
        # First, check ability buttons via render system layout cache if available
        render_system = getattr(self.window, 'render_system', None)
        if render_system and hasattr(render_system, 'get_ability_at_point'):
            entry = render_system.get_ability_at_point(x, y)
            if entry and self.world is not None:
                # owner_entity now embedded in layout entry for multi-owner support
                owner_entity = entry.get('owner_entity')
                if owner_entity is not None:
                    self.event_bus.emit(
                        EVENT_ABILITY_ACTIVATE_REQUEST,
                        ability_entity=entry['entity'],
                        owner_entity=owner_entity,
                    )
                    return  # Do not treat as tile click
        # Otherwise treat as board click if within bounds
        if hasattr(self.window, 'render_system'):
            tile_size, start_x, start_y = compute_board_geometry(self.window.width, self.window.height)
        else:
            # Legacy fallback (tests without render system expect static TILE_SIZE centering)
            from ecs.constants import TILE_SIZE, BOTTOM_MARGIN
            tile_size = TILE_SIZE
            total_width = GRID_COLS * tile_size
            start_x = (self.window.width - total_width) / 2
            start_y = BOTTOM_MARGIN
        total_width = GRID_COLS * tile_size
        if x < start_x or x > start_x + total_width:
            return
        if y < start_y or y > start_y + GRID_ROWS * tile_size:
            return
        col = int((x - start_x) // tile_size)
        row = int((y - start_y) // tile_size)
        if 0 <= row < GRID_ROWS and 0 <= col < GRID_COLS:
            self.event_bus.emit(EVENT_TILE_CLICK, row=row, col=col)
