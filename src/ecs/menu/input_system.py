"""Input handling for the ECS-driven main menu."""
from esper import World

from ecs.components.game_state import GameMode, GameState
from ecs.events.bus import EVENT_MOUSE_PRESS, EventBus
from ecs.menu.components import MenuAction, MenuBackground, MenuButton, MenuTag
from ecs.factories.abilities import spawn_starting_ability_choice


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
        self.handle_mouse_press(float(x), float(y), int(button))

    def handle_mouse_press(self, x: float, y: float, button: int) -> None:
        """Handle mouse clicks; start game if the button is activated."""
        state = self._get_game_state()
        if not state or state.mode != GameMode.MENU:
            return

        for entity, menu_button in self.world.get_component(MenuButton):
            if self._point_inside_button(x, y, menu_button):
                if menu_button.action == MenuAction.NEW_GAME:
                    state.mode = GameMode.ABILITY_DRAFT
                    self._clear_menu_entities()
                    spawn_starting_ability_choice(self.world)
                return

    def handle_key_press(self, symbol: int, modifiers: int) -> None:
        """Allow keyboard activation using the Enter key."""
        state = self._get_game_state()
        if not state or state.mode != GameMode.MENU:
            return
        # arcade.key.ENTER == 65293, but we avoid direct import to keep loose coupling.
        if symbol in (65293, 13):
            state.mode = GameMode.ABILITY_DRAFT
            self._clear_menu_entities()
            spawn_starting_ability_choice(self.world)

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

    @staticmethod
    def _point_inside_button(x: float, y: float, button: MenuButton) -> bool:
        half_w = button.width / 2
        half_h = button.height / 2
        return (
            button.x - half_w <= x <= button.x + half_w
            and button.y - half_h <= y <= button.y + half_h
        )
