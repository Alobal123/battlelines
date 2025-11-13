from __future__ import annotations

from typing import TYPE_CHECKING

from ecs.components.tile_bank import TileBank
from ecs.constants import (
    BANK_BAR_HEIGHT,
    BANK_BAR_EXTRA_HEIGHT,
    PLAYER_PANEL_HEIGHT,
    SIDE_GAP,
    SIDE_PANEL_MIN_WIDTH,
    SIDE_PANEL_TOP_MARGIN,
)

if TYPE_CHECKING:
    from ecs.components.tile_types import TileTypes
    from ecs.rendering.context import RenderContext
    from ecs.rendering.sprite_cache import SpriteCache
    from ecs.systems.render import RenderSystem


class BankPanelRenderer:
    def __init__(self, render_system: RenderSystem, sprite_cache: "SpriteCache"):
        self._rs = render_system
        self._sprites = sprite_cache

    def render(self, arcade, ctx: RenderContext, registry: TileTypes) -> None:
        rs = self._rs
        board_left = ctx.board_left
        board_right = ctx.board_right
        # Expand side panels upward nearly to top of window (keep small margin)
        side_panel_top = ctx.window_height - SIDE_PANEL_TOP_MARGIN
        board_start_y = ctx.board_bottom
        banks = list(rs.world.get_component(TileBank))
        if not banks:
            return
        banks_sorted = sorted(banks, key=lambda pair: pair[1].owner_entity)
        visible_types = {"tactics", "subterfuge", "support", "engineering"}
        window_w = ctx.window_width
        left_space = max(0, board_left - SIDE_GAP)
        right_space = max(0, (window_w - board_right) - SIDE_GAP)
        left_col_w = max(SIDE_PANEL_MIN_WIDTH, left_space)
        right_col_w = max(SIDE_PANEL_MIN_WIDTH, right_space)
        left_panel_left = board_left - SIDE_GAP - left_col_w
        right_panel_left = board_right + SIDE_GAP
        panel_bottom = board_start_y
        panel_top = side_panel_top
        panel_color = (20, 20, 20)
        border_color = (180, 180, 180)

        # Bank bar sits below external player panel renderer; include configured extra height.
        bar_height = BANK_BAR_HEIGHT + BANK_BAR_EXTRA_HEIGHT
        for side, col_w in (("left", left_col_w), ("right", right_col_w)):
            x = left_panel_left if side == "left" else right_panel_left
            ability_bottom = panel_bottom
            ability_top = panel_top - (PLAYER_PANEL_HEIGHT + bar_height)
            points = [
                (x, ability_bottom), (x + col_w, ability_bottom),
                (x + col_w, ability_top), (x, ability_top),
            ]
            arcade.draw_polygon_filled(points, panel_color)
            arcade.draw_polygon_outline(points, border_color, 2)
            # Bank bar directly below (player panel rendered separately)
            bar_top = panel_top - PLAYER_PANEL_HEIGHT
            bar_bottom = bar_top - bar_height
            bar_points = [
                (x, bar_bottom), (x + col_w, bar_bottom),
                (x + col_w, bar_top), (x, bar_top),
            ]
            arcade.draw_polygon_filled(bar_points, (35, 35, 35))
            arcade.draw_polygon_outline(bar_points, border_color, 2)

        circle_radius = 32
        ordered_types = ["tactics", "support", "engineering", "subterfuge"]
        for idx, (bank_ent, bank) in enumerate(banks_sorted):
            bar_left = left_panel_left if idx == 0 else right_panel_left
            bar_bottom = panel_top - PLAYER_PANEL_HEIGHT - bar_height
            # Center circles vertically inside bank bar
            bar_top = panel_top - PLAYER_PANEL_HEIGHT
            center_y = (bar_bottom + bar_top) / 2
            col_w = left_col_w if idx == 0 else right_col_w
            pad_left = bar_left + 48  # increased left gutter
            pad_right = bar_left + col_w - 48  # increased right gutter
            span_width = max(0, pad_right - pad_left)
            slots = len(ordered_types)
            if slots <= 1:
                positions = [pad_left + span_width / 2]
            else:
                step = span_width / (slots - 1)
                positions = [pad_left + i * step for i in range(slots)]
            for type_name, cx in zip(ordered_types, positions):
                if type_name not in visible_types:
                    continue
                count = bank.counts.get(type_name, 0)
                try:
                    color_tuple = registry.background_for(type_name)
                except Exception:
                    color_tuple = (80, 80, 80)
                arcade.draw_circle_filled(cx, center_y, circle_radius, color_tuple)
                arcade.draw_circle_outline(cx, center_y, circle_radius, (255, 255, 255), 2)
                icon_sprite = self._sprites.ensure_bank_sprite(arcade, bank_ent, type_name)
                if icon_sprite is not None:
                    self._sprites.update_sprite_visuals(icon_sprite, cx, center_y, circle_radius * 1.2, 255)
                # Place count just below circle bottom, remain inside bar
                text_y = center_y - circle_radius - 6
                arcade.draw_text(str(count), cx, text_y, arcade.color.WHITE, 16, anchor_x="center")

        self._sprites.draw_bank_sprites()
