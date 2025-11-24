from ecs.events.bus import (
    EventBus,
    EVENT_MOUSE_PRESS,
    EVENT_TILE_CLICK,
    EVENT_ABILITY_ACTIVATE_REQUEST,
    EVENT_TILE_BANK_GAINED,
    EVENT_HEALTH_DAMAGE,
)
from ecs.constants import GRID_COLS, GRID_ROWS
from ecs.ui.layout import compute_board_geometry
from ecs.components.active_turn import ActiveTurn
from ecs.components.human_agent import HumanAgent
from ecs.components.choice_window import ChoiceWindow
from ecs.components.game_state import GameMode, GameState
from ecs.components.tile_bank import TileBank
from ecs.components.health import Health

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
        if not self._combat_mode_active():
            return
        if self._choice_window_active():
            return
        active_owner = self._active_owner()
        active_human_owner = active_owner if self._is_human_entity(active_owner) else None
        input_locked = active_owner is not None and active_human_owner is None
        # Left button (1) drives activation or tile clicks. Other buttons fall through (so right-click can be handled by other systems).
        if button != 1:
            if button == 4 and input_locked:
                return
            return  # Do not emit tile click or ability activation for non-left buttons; Board/Ability systems listen directly to EVENT_MOUSE_PRESS
        # First, check for portrait hits to support debug damage taps
        render_system = getattr(self.window, 'render_system', None)
        if render_system and hasattr(render_system, 'get_player_panel_at_point'):
            panel_entry = render_system.get_player_panel_at_point(x, y)
            if panel_entry:
                owner_entity = panel_entry.get('owner_entity')
                if self.world is not None and owner_entity is not None:
                    try:
                        self.world.component_for_entity(owner_entity, Health)
                    except KeyError:
                        pass
                    else:
                        self.event_bus.emit(
                            EVENT_HEALTH_DAMAGE,
                            target_entity=owner_entity,
                            amount=10,
                            reason="portrait_click_debug",
                            source_owner=active_owner,
                        )
                return
        # Next, check ability buttons via render system layout cache if available
        if render_system and hasattr(render_system, 'get_ability_at_point'):
            entry = render_system.get_ability_at_point(x, y)
            if entry and self.world is not None and not input_locked:
                usable = entry.get('usable')
                if usable is None:
                    usable = entry.get('affordable', True) and entry.get('cooldown_remaining', 0) <= 0
                if not usable:
                    return
                # owner_entity now embedded in layout entry for multi-owner support
                owner_entity = entry.get('owner_entity')
                if owner_entity is not None:
                    if active_owner is not None:
                        if owner_entity != active_human_owner:
                            return
                    elif not self._is_human_entity(owner_entity):
                        return
                    self.event_bus.emit(
                        EVENT_ABILITY_ACTIVATE_REQUEST,
                        ability_entity=entry['entity'],
                        owner_entity=owner_entity,
                    )
                    return  # Do not treat as tile click
        if render_system and hasattr(render_system, 'get_forbidden_knowledge_at_point'):
            bar_entry = render_system.get_forbidden_knowledge_at_point(x, y)
            if bar_entry is not None:
                bank_info = self._human_bank_target()
                if bank_info is not None:
                    bank_ent, owner = bank_info
                    self.event_bus.emit(
                        EVENT_TILE_BANK_GAINED,
                        owner_entity=owner,
                        bank_entity=bank_ent,
                        type_name='secrets',
                        amount=1,
                        source='knowledge_bar_click',
                    )
                return
        if render_system and hasattr(render_system, 'get_bank_icon_at_point'):
            bank_entry = render_system.get_bank_icon_at_point(x, y)
            if bank_entry:
                owner_entity = bank_entry.get('owner_entity')
                type_name = bank_entry.get('type_name')
                if owner_entity is not None and isinstance(type_name, str) and type_name:
                    amount = bank_entry.get('amount', 1)
                    try:
                        amount_int = int(amount)
                    except (TypeError, ValueError):
                        amount_int = 1
                    if amount_int <= 0:
                        amount_int = 1
                    self.event_bus.emit(
                        EVENT_TILE_BANK_GAINED,
                        owner_entity=owner_entity,
                        bank_entity=bank_entry.get('bank_entity'),
                        type_name=type_name,
                        amount=amount_int,
                        source="bank_click",
                    )
                return
        # (Legacy regiment click handling removed.)
        # Otherwise treat as board click if within bounds
        if input_locked:
            return
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

    def _choice_window_active(self) -> bool:
        if self.world is None:
            return False
        return any(True for _ in self.world.get_component(ChoiceWindow))

    def _combat_mode_active(self) -> bool:
        if self.world is None:
            return True
        states = list(self.world.get_component(GameState))
        if not states:
            return True
        return states[0][1].mode == GameMode.COMBAT

    def _active_owner(self):
        if self.world is None:
            return None
        active = list(self.world.get_component(ActiveTurn))
        if not active:
            return None
        return active[0][1].owner_entity

    def _is_human_entity(self, entity):
        if self.world is None or entity is None:
            return False
        try:
            self.world.component_for_entity(entity, HumanAgent)
            return True
        except KeyError:
            return False

    def _human_bank_target(self):
        if self.world is None:
            return None
        for bank_ent, bank in self.world.get_component(TileBank):
            owner = bank.owner_entity
            if self._is_human_entity(owner):
                return bank_ent, owner
        return None
