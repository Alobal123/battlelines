"""Input handling for the ECS-driven main menu."""
from esper import World

from ecs.components.game_state import GameMode, GameState
from ecs.events.bus import (
    EVENT_MENU_CONTINUE_SELECTED,
    EVENT_MENU_NEW_GAME_SELECTED,
    EVENT_MOUSE_PRESS,
    EventBus,
)
from ecs.menu.components import MenuAction, MenuBackground, MenuButton, MenuTag


class MenuInputSystem:
    """Processes input events while the game is in the menu mode."""

    def __init__(self, world: World, event_bus: EventBus | None = None) -> None:
        self.world = world
        self._event_bus = event_bus
        if event_bus is not None:
            event_bus.subscribe(EVENT_MOUSE_PRESS, self.on_mouse_press)

    def on_mouse_press(self, sender, **payload) -> None:
        x = payload.get("x")
        y = payload.get("y")
        button = payload.get("button")
        if x is None or y is None or button is None:
            return
        press_id = payload.get("press_id")
        try:
            press_id_int = int(press_id) if press_id is not None else None
        except (TypeError, ValueError):
            press_id_int = None
        self.handle_mouse_press(float(x), float(y), int(button), press_id_int)

    def handle_mouse_press(
        self,
        x: float,
        y: float,
        button: int,
        press_id: int | None = None,
    ) -> None:
        """Handle mouse clicks; start game if the button is activated."""
        state = self._get_game_state()
        if not state or state.mode != GameMode.MENU:
            return

        for _, menu_button in self.world.get_component(MenuButton):
            if not menu_button.enabled:
                continue
            if self._point_inside_button(x, y, menu_button):
                self._activate_action(menu_button.action, press_id=press_id)
                return

    def handle_key_press(self, symbol: int, modifiers: int) -> None:
        """Allow keyboard activation using the Enter key."""
        state = self._get_game_state()
        if not state or state.mode != GameMode.MENU:
            return
        # arcade.key.ENTER == 65293, but we avoid direct import to keep loose coupling.
        if symbol in (65293, 13):
            self._activate_action(MenuAction.NEW_GAME)

    def _activate_action(self, action: MenuAction, *, press_id: int | None = None) -> None:
        if action == MenuAction.NEW_GAME:
            self._handle_new_game_selection(press_id=press_id)
        elif action == MenuAction.CONTINUE:
            self._handle_continue_selection(press_id=press_id)

    def _clear_menu_entities(self) -> None:
        """Remove all entities that are part of the menu UI."""
        to_delete: set[int] = set()
        for ent, _ in self.world.get_component(MenuButton):
            to_delete.add(ent)
        for ent, _ in self.world.get_component(MenuBackground):
            to_delete.add(ent)
        for ent, _ in self.world.get_component(MenuTag):
            to_delete.add(ent)
        for ent in to_delete:
            self.world.delete_entity(ent)

    def _get_game_state(self) -> GameState | None:
        for _, state in self.world.get_component(GameState):
            return state
        return None

    def _handle_new_game_selection(self, *, press_id: int | None = None) -> None:
        state = self._get_game_state()
        if state and state.mode == GameMode.MENU:
            self._emit(EVENT_MENU_NEW_GAME_SELECTED, press_id=press_id)
            self._clear_menu_entities()
            if self._event_bus is None:
                state.mode = GameMode.ABILITY_DRAFT
                state.input_guard_press_id = press_id
                from ecs.factories.abilities import spawn_player_ability_choice

                spawn_player_ability_choice(
                    self.world,
                    event_bus=None,
                    require_empty_owner=True,
                    title="Choose Your First Ability",
                    press_id=press_id,
                )

    def _handle_continue_selection(self, *, press_id: int | None = None) -> None:
        state = self._get_game_state()
        if state and state.mode == GameMode.MENU:
            self._emit(EVENT_MENU_CONTINUE_SELECTED, press_id=press_id)
            self._clear_menu_entities()
            if self._event_bus is None:
                state.mode = GameMode.ABILITY_DRAFT
                state.input_guard_press_id = press_id
                from ecs.factories.abilities import spawn_player_ability_choice

                spawn_player_ability_choice(
                    self.world,
                    event_bus=None,
                    require_empty_owner=True,
                    title="Choose Your First Ability",
                    press_id=press_id,
                )

    def _emit(self, name: str, *, press_id: int | None = None) -> None:
        if self._event_bus is not None:
            if press_id is not None:
                self._event_bus.emit(name, press_id=press_id)
            else:
                self._event_bus.emit(name)

    @staticmethod
    def _point_inside_button(x: float, y: float, button: MenuButton) -> bool:
        half_w = button.width / 2
        half_h = button.height / 2
        return (
            button.x - half_w <= x <= button.x + half_w
            and button.y - half_h <= y <= button.y + half_h
        )
