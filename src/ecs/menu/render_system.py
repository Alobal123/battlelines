"""Rendering system responsible for drawing the main menu."""
import arcade
from esper import World
from ecs.components.game_state import GameState, GameMode
from ecs.menu.components import MenuBackground, MenuButton


class MenuRenderSystem:
    """Renders menu entities when the game is in menu mode."""

    def __init__(self, world: World, window) -> None:
        self.world = world
        self.window = window

    def process(self) -> None:
        """Draw the menu if the current mode is Menu."""
        state = self._get_game_state()
        if not state or state.mode != GameMode.MENU:
            return

        # Fill background
        for _, background in self.world.get_component(MenuBackground):
            arcade.draw_lrbt_rectangle_filled(
                0,
                self.window.width,
                0,
                self.window.height,
                background.color,
            )

        # Draw buttons
        for _, button in self.world.get_component(MenuButton):
            left = button.x - button.width / 2
            bottom = button.y - button.height / 2
            fill_color = arcade.color.DARK_SLATE_BLUE if button.enabled else arcade.color.GRAY_BLUE
            outline_color = arcade.color.WHITE if button.enabled else arcade.color.SILVER
            text_color = arcade.color.WHITE if button.enabled else arcade.color.SILVER
            arcade.draw_lbwh_rectangle_filled(
                left,
                bottom,
                button.width,
                button.height,
                fill_color,
            )
            arcade.draw_lbwh_rectangle_outline(
                left,
                bottom,
                button.width,
                button.height,
                outline_color,
                border_width=2,
            )
            arcade.draw_text(
                button.label,
                button.x,
                button.y,
                text_color,
                24,
                anchor_x="center",
                anchor_y="center",
                bold=True,
            )

    def _get_game_state(self) -> GameState | None:
        for _, state in self.world.get_component(GameState):
            return state
        return None
