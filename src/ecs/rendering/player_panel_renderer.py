from __future__ import annotations

from typing import TYPE_CHECKING

from ecs.constants import PLAYER_PANEL_HEIGHT, SIDE_GAP, SIDE_PANEL_MIN_WIDTH, SIDE_PANEL_TOP_MARGIN
from ecs.components.ability_list_owner import AbilityListOwner

if TYPE_CHECKING:
    from ecs.rendering.context import RenderContext
    from ecs.systems.render import RenderSystem


class PlayerPanelRenderer:
    """Renders a simple player header strip above the bank bar.

    Future extension: show dynamic player names, scores, turn indicators, icons.
    """
    def __init__(self, render_system: RenderSystem):
        self._rs = render_system

    def render(self, arcade, ctx: 'RenderContext') -> None:
        board_left = ctx.board_left
        board_right = ctx.board_right
        # Extend player panel upward near top of window (small margin)
        panel_top = ctx.window_height - SIDE_PANEL_TOP_MARGIN
        window_w = ctx.window_width
        left_space = max(0, board_left - SIDE_GAP)
        right_space = max(0, (window_w - board_right) - SIDE_GAP)
        left_col_w = max(SIDE_PANEL_MIN_WIDTH, left_space)
        right_col_w = max(SIDE_PANEL_MIN_WIDTH, right_space)
        left_panel_left = board_left - SIDE_GAP - left_col_w
        right_panel_left = board_right + SIDE_GAP

        panel_color = (50, 50, 50)
        border_color = (180, 180, 180)

        rs = self._rs
        rs._player_panel_cache = []
        owners = list(rs.world.get_component(AbilityListOwner))
        owners.sort(key=lambda item: item[0])
        owner_by_side: dict[str, int] = {}
        for idx, (entity, _owner_comp) in enumerate(owners):
            if idx == 0:
                owner_by_side["left"] = entity
            elif idx == 1:
                owner_by_side["right"] = entity
            else:
                break

        for side, col_w in (("left", left_col_w), ("right", right_col_w)):
            x = left_panel_left if side == "left" else right_panel_left
            player_bottom = panel_top - PLAYER_PANEL_HEIGHT
            player_points = [
                (x, player_bottom), (x + col_w, player_bottom),
                (x + col_w, panel_top), (x, panel_top),
            ]
            arcade.draw_polygon_filled(player_points, panel_color)
            arcade.draw_polygon_outline(player_points, border_color, 2)
            label = "Player 1" if side == "left" else "Player 2"
            arcade.draw_text(label, x + col_w / 2, player_bottom + PLAYER_PANEL_HEIGHT / 2 - 8,
                             arcade.color.WHITE, 16, anchor_x="center")
            owner_entity = owner_by_side.get(side)
            if owner_entity is not None:
                rs._player_panel_cache.append(
                    {
                        "side": side,
                        "owner_entity": owner_entity,
                        "x": x,
                        "y": player_bottom,
                        "width": col_w,
                        "height": PLAYER_PANEL_HEIGHT,
                        "label": label,
                    }
                )
