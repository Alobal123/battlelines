from __future__ import annotations

from typing import TYPE_CHECKING

from ecs.components.tile_bank import TileBank
from ecs.constants import (
    ABILITY_TOP_PADDING,
    BANK_BAR_HEIGHT,
    BANK_BAR_EXTRA_HEIGHT,
    PLAYER_PANEL_HEIGHT,
    SIDE_GAP,
    SIDE_PANEL_INNER_PAD,
    SIDE_PANEL_MIN_WIDTH,
    SIDE_PANEL_TOP_MARGIN,
)

if TYPE_CHECKING:
    from ecs.rendering.context import RenderContext
    from ecs.systems.render import RenderSystem


class AbilityPanelRenderer:
    def __init__(self, render_system: RenderSystem):
        self._rs = render_system

    def render(self, arcade, ctx: RenderContext, headless: bool) -> None:
        """Build ability layout entries and draw the ability panel."""
        rs = self._rs
        from ecs.components.ability import Ability

        ability_comps = list(rs.world.get_component(Ability))
        if not ability_comps:
            rs._ability_layout_cache = []
            return

        from ecs.components.ability_list_owner import AbilityListOwner
        from ecs.ui.ability_layout import compute_ability_layout

        owners = list(rs.world.get_component(AbilityListOwner))
        owners.sort(key=lambda item: item[0])

        rect_h = 44  # reduced height for more space to bank bar
        spacing = 8
        board_left = ctx.board_left
        board_right = ctx.board_right
        # Use expanded side panel top (near window top) for ability panel stacking
        side_panel_top = ctx.window_height - SIDE_PANEL_TOP_MARGIN
        window_w = ctx.window_width
        left_space = max(0, board_left - SIDE_GAP)
        right_space = max(0, (window_w - board_right) - SIDE_GAP)
        left_col_w = max(SIDE_PANEL_MIN_WIDTH, left_space)
        right_col_w = max(SIDE_PANEL_MIN_WIDTH, right_space)
        # Account for player panel + bank (with extra breathing room) stacked above abilities.
        ability_panel_top = side_panel_top - (PLAYER_PANEL_HEIGHT + BANK_BAR_HEIGHT + BANK_BAR_EXTRA_HEIGHT)
        first_rect_bottom = ability_panel_top - ABILITY_TOP_PADDING - rect_h
        left_rect_w = max(60, left_col_w - 2 * SIDE_PANEL_INNER_PAD)
        right_rect_w = max(60, right_col_w - 2 * SIDE_PANEL_INNER_PAD)
        left_panel_x = board_left - SIDE_GAP - left_col_w + SIDE_PANEL_INNER_PAD
        right_panel_x = board_right + SIDE_GAP + SIDE_PANEL_INNER_PAD
        banks = {bank.owner_entity: bank.counts for _, bank in rs.world.get_component(TileBank)}
        rs._ability_layout_cache = []
        for col_index, (owner_ent, owner_comp) in enumerate(owners):
            owner_abilities = [
                (ent, ability)
                for (ent, ability) in ability_comps
                if ent in owner_comp.ability_entities
            ]
            counts = banks.get(owner_ent, {})
            panel_x = left_panel_x if col_index == 0 else right_panel_x
            rect_w = left_rect_w if col_index == 0 else right_rect_w
            layout_entries = compute_ability_layout(
                owner_abilities,
                counts,
                owner_entity=owner_ent,
                start_x=panel_x,
                start_top=first_rect_bottom,
                rect_w=rect_w,
                rect_h=rect_h,
                spacing=spacing,
            )
            rs._ability_layout_cache.extend(layout_entries)

        targeting_ability_entity = None
        try:
            from ecs.components.targeting_state import TargetingState

            targeting_states = list(rs.world.get_component(TargetingState))
            if targeting_states:
                targeting_ability_entity = targeting_states[0][1].ability_entity
        except Exception:
            targeting_ability_entity = None

        for entry in rs._ability_layout_cache:
            entry["is_targeting"] = (
                targeting_ability_entity is not None and entry["entity"] == targeting_ability_entity
            )
            entry["is_active"] = (
                rs._current_active_owner is not None and entry["owner_entity"] == rs._current_active_owner
            )

        for entry in rs._ability_layout_cache:
            x = entry["x"]
            y = entry["y"]
            w = entry["width"]
            h = entry["height"]
            affordable = entry["affordable"]
            base_color = (40, 100, 40) if affordable else (120, 40, 40)
            if entry["is_active"] and not entry["is_targeting"]:
                r, g, b = base_color
                bg_color = (min(255, r + 30), min(255, g + 30), min(255, b + 30))
            else:
                bg_color = base_color
            border_color = (200, 200, 200)
            points = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            if headless:
                continue
            if hasattr(arcade, "draw_polygon_filled"):
                if entry["is_targeting"]:
                    arcade.draw_polygon_filled(points, (70, 130, 180))
                else:
                    arcade.draw_polygon_filled(points, bg_color)
                if hasattr(arcade, "draw_polygon_outline"):
                    if entry["is_targeting"]:
                        arcade.draw_polygon_outline(points, arcade.color.LIGHT_BLUE, 3)
                    elif entry["is_active"]:
                        arcade.draw_polygon_outline(points, (150, 200, 255), 2)
                    else:
                        arcade.draw_polygon_outline(points, border_color, 2)
            else:
                arcade.draw_circle_filled(x + w / 2, y + h / 2, w / 2, bg_color)
                arcade.draw_circle_outline(x + w / 2, y + h / 2, w / 2, border_color, 2)
            name_y = y + h - 16
            arcade.draw_text(entry["name"], x + 8, name_y, arcade.color.WHITE, 14)
            cost_line = " ".join(f"{ctype}:{cval}" for ctype, cval in entry["cost"].items())
            arcade.draw_text(cost_line, x + 8, y + 8, arcade.color.WHITE, 12)

    def hit_test(self, x: float, y: float):
        for entry in getattr(self._rs, "_ability_layout_cache", []):
            ex, ey, w, h = entry["x"], entry["y"], entry["width"], entry["height"]
            if ex <= x <= ex + w and ey <= y <= ey + h:
                return entry
        return None
