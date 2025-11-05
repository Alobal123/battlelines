from ecs.events.bus import EventBus, EVENT_MOUSE_PRESS, EVENT_TILE_CLICK, EVENT_ABILITY_ACTIVATE_REQUEST
from ecs.constants import GRID_COLS, GRID_ROWS, TILE_SIZE, BOTTOM_MARGIN

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
                from ecs.components.ability_list_owner import AbilityListOwner
                owners = list(self.world.get_component(AbilityListOwner))
                if owners:
                    owner_ent, owner_comp = owners[0]
                    if entry['entity'] in owner_comp.ability_entities:
                        self.event_bus.emit(
                            EVENT_ABILITY_ACTIVATE_REQUEST,
                            ability_entity=entry['entity'],
                            owner_entity=owner_ent,
                        )
                        return  # Do not treat as tile click
        # Otherwise treat as board click if within bounds
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
