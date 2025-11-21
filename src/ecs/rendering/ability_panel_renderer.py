from __future__ import annotations

from typing import TYPE_CHECKING

from ecs.components.tile_bank import TileBank
from ecs.components.ability_cooldown import AbilityCooldown
from ecs.constants import (
    ABILITY_TOP_PADDING,
    BANK_BAR_HEIGHT,
    BANK_BAR_EXTRA_HEIGHT,
    PLAYER_PANEL_HEIGHT,
    PLAYER_PORTRAIT_PADDING,
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
        self._active_cost_icon_keys: set[tuple[int, int]] = set()

    def render(self, arcade, ctx: RenderContext, headless: bool) -> None:
        """Build ability layout entries and draw the ability panel."""
        rs = self._rs
        from ecs.components.ability import Ability

        ability_comps = list(rs.world.get_component(Ability))
        if not ability_comps:
            rs._ability_layout_cache = []
            return

        ability_map = {ent: ability for ent, ability in ability_comps}

        from ecs.components.ability_list_owner import AbilityListOwner
        from ecs.ui.ability_layout import compute_ability_layout

        owners = list(rs.world.get_component(AbilityListOwner))
        owners.sort(key=lambda item: item[0])

        rows_to_fit = 4
        row_spacing = 6.0
        column_spacing = 12.0
        min_cell_width = 84.0
        max_columns = 2
        board_left = ctx.board_left
        board_right = ctx.board_right
        # Use expanded side panel top (near window top) for ability panel stacking
        side_panel_top = ctx.window_height - SIDE_PANEL_TOP_MARGIN
        window_w = ctx.window_width
        left_space = max(0, board_left - SIDE_GAP)
        right_space = max(0, (window_w - board_right) - SIDE_GAP)
        left_col_w = max(SIDE_PANEL_MIN_WIDTH, left_space)
        right_col_w = max(SIDE_PANEL_MIN_WIDTH, right_space)
        # Account for player panel, portrait (using full column width), and bank stacked above abilities.
        portrait_block = max(left_col_w, right_col_w) + PLAYER_PORTRAIT_PADDING
        ability_panel_top = side_panel_top - (
            PLAYER_PANEL_HEIGHT + portrait_block + BANK_BAR_HEIGHT + BANK_BAR_EXTRA_HEIGHT
        )
        ability_bottom = ctx.board_bottom
        ability_top_line = ability_panel_top - ABILITY_TOP_PADDING
        available_vertical = max(0.0, ability_top_line - ability_bottom)
        spacing_total = row_spacing * max(0, rows_to_fit - 1)
        if rows_to_fit > 0 and available_vertical > 0:
            usable_vertical = max(0.0, available_vertical - spacing_total)
            if usable_vertical > 0:
                rect_h = usable_vertical / rows_to_fit
            else:
                rect_h = available_vertical / rows_to_fit
        else:
            rect_h = 0.0
        if rect_h <= 0:
            rect_h = 40.0
        first_rect_bottom = ability_top_line - rect_h
        left_available_w = max(60, left_col_w - 2 * SIDE_PANEL_INNER_PAD)
        right_available_w = max(60, right_col_w - 2 * SIDE_PANEL_INNER_PAD)
        left_panel_x = board_left - SIDE_GAP - left_col_w + SIDE_PANEL_INNER_PAD
        right_panel_x = board_right + SIDE_GAP + SIDE_PANEL_INNER_PAD
        banks = {bank.owner_entity: bank.counts for _, bank in rs.world.get_component(TileBank)}
        try:
            tile_types = self._rs._registry()
        except Exception:
            tile_types = None
        rs._ability_layout_cache = []
        sprite_cache = getattr(self._rs, "sprite_cache", None)
        self._active_cost_icon_keys = set()

        for col_index, (owner_ent, owner_comp) in enumerate(owners):
            owner_abilities = [
                (ent, ability)
                for (ent, ability) in ability_comps
                if ent in owner_comp.ability_entities
            ]
            counts = banks.get(owner_ent, {})
            panel_x = left_panel_x if col_index == 0 else right_panel_x
            available_width = left_available_w if col_index == 0 else right_available_w
            panel_columns = max_columns
            required_width = min_cell_width * panel_columns + column_spacing * (panel_columns - 1)
            if available_width < required_width:
                panel_columns = 1
            if panel_columns > 1:
                rect_w = (available_width - column_spacing * (panel_columns - 1)) / panel_columns
                active_column_spacing = column_spacing
            else:
                rect_w = available_width
                active_column_spacing = 0.0
            max_visible = rows_to_fit * panel_columns if panel_columns > 0 else 0
            if max_visible and len(owner_abilities) > max_visible:
                owner_abilities = owner_abilities[:max_visible]
            layout_entries = compute_ability_layout(
                owner_abilities,
                counts,
                owner_entity=owner_ent,
                start_x=panel_x,
                start_top=first_rect_bottom,
                rect_w=rect_w,
                rect_h=rect_h,
                spacing=row_spacing,
                columns=panel_columns,
                column_spacing=active_column_spacing,
            )
            for entry in layout_entries:
                ability_entity = entry["entity"]
                ability = ability_map.get(ability_entity)
                base_cooldown = ability.cooldown if ability else 0
                entry["cooldown"] = base_cooldown
                try:
                    cooldown_state = rs.world.component_for_entity(ability_entity, AbilityCooldown)
                    remaining = max(0, int(cooldown_state.remaining_turns))
                except KeyError:
                    remaining = 0
                entry["cooldown_remaining"] = remaining
                entry["resource_affordable"] = entry["affordable"]
                entry["usable"] = entry["affordable"] and remaining <= 0
                entry["cooldown_blocked"] = remaining > 0
                rs._ability_layout_cache.append(entry)

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
            resource_ok = entry.get("resource_affordable", True)
            cooldown_remaining = entry.get("cooldown_remaining", 0)
            usable = entry.get("usable", resource_ok and cooldown_remaining <= 0)
            base_color = (40, 100, 40)
            if not resource_ok:
                base_color = (120, 40, 40)
            elif cooldown_remaining > 0:
                base_color = (80, 80, 80)
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
            label = entry.get("name") or entry.get("slug", "")
            arcade.draw_text(label, x + 8, name_y, arcade.color.WHITE, 14)
            if entry["cost"]:
                self._draw_cost_icons(
                    arcade,
                    tile_types,
                    entry["cost"],
                    ability_entity=entry["entity"],
                    start_x=x + 8,
                    start_y=y + 8,
                    dimmed=not usable,
                )
            base_cd = entry.get("cooldown", 0)
            remaining_cd = entry.get("cooldown_remaining", 0)
            if base_cd > 0:
                if remaining_cd > 0:
                    cd_text = f"CD {remaining_cd}"
                    cd_color = arcade.color.LIGHT_GRAY
                else:
                    cd_text = f"CD {base_cd}"
                    cd_color = arcade.color.GRAY
                arcade.draw_text(cd_text, x + w - 8, y + h - 20, cd_color, 12, anchor_x="right")

        if not headless and sprite_cache is not None:
            sprite_cache.draw_ability_cost_sprites()
            sprite_cache.cleanup_ability_cost_sprites(self._active_cost_icon_keys)
        elif sprite_cache is not None:
            sprite_cache.cleanup_ability_cost_sprites(set())

    def hit_test(self, x: float, y: float):
        for entry in getattr(self._rs, "_ability_layout_cache", []):
            ex, ey, w, h = entry["x"], entry["y"], entry["width"], entry["height"]
            if ex <= x <= ex + w and ey <= y <= ey + h:
                return entry
        return None

    def _draw_cost_icons(
        self,
        arcade,
        tile_types,
        cost: dict[str, int],
        *,
        ability_entity: int,
        start_x: float,
        start_y: float,
    icon_size: float = 30.0,
    spacing: float = 16.0,
        dimmed: bool = False,
    ) -> None:
        if not cost:
            return
        x = start_x
        y = start_y
        text_base_color = (200, 200, 200) if dimmed else (255, 255, 255)
        outline_color = (90, 90, 110) if dimmed else (255, 255, 255)
        sprite_cache = getattr(self._rs, "sprite_cache", None)
        for slot_index, (type_name, amount) in enumerate(sorted(cost.items())):
            if amount <= 0:
                continue
            try:
                base_color = tile_types.background_for(type_name) if tile_types is not None else None
            except Exception:
                base_color = None
            if base_color is None:
                base_color = (110, 110, 120)
            if dimmed:
                base_color = tuple(min(255, max(0, int(c * 0.45 + 40))) for c in base_color)
            center_x = x + icon_size / 2.0
            center_y = y + icon_size / 2.0
            radius = icon_size / 2.0
            left = center_x - radius
            right = center_x + radius
            arcade.draw_circle_filled(center_x, center_y, radius, base_color)
            arcade.draw_circle_outline(center_x, center_y, radius, outline_color, 1)
            sprite = None
            if (
                sprite_cache is not None
                and hasattr(sprite_cache, "ensure_ability_cost_sprite")
            ):
                sprite = sprite_cache.ensure_ability_cost_sprite(arcade, ability_entity, slot_index, type_name)
                if sprite is not None and hasattr(sprite_cache, "update_sprite_visuals"):
                    sprite_cache.update_sprite_visuals(sprite, center_x, center_y, icon_size, 255)
            if sprite is not None:
                self._active_cost_icon_keys.add((ability_entity, slot_index))
            amount_str = str(int(amount))
            text_y = center_y - 8
            arcade.draw_text(amount_str, right + 4.0, text_y, text_base_color, 12)
            text_width = max(len(amount_str) * 7.0, 10.0)
            x = right + 4.0 + text_width + spacing
