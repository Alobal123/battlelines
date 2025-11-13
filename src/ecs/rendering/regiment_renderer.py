from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ecs.components.army_roster import ArmyRoster
from ecs.components.regiment import Regiment
from ecs.constants import SIDE_GAP, SIDE_PANEL_MIN_WIDTH

if TYPE_CHECKING:
    from ecs.components.tile_types import TileTypes
    from ecs.rendering.context import RenderContext
    from ecs.rendering.sprite_cache import SpriteCache
    from ecs.systems.render import RenderSystem


class RegimentRenderer:
    def __init__(self, render_system: RenderSystem, sprite_cache: "SpriteCache"):
        self._rs = render_system
        self._sprites = sprite_cache

    def render(self, arcade, ctx: RenderContext, registry: TileTypes) -> None:
        rs = self._rs
        sprites = self._sprites
        rosters = sorted(rs.world.get_component(ArmyRoster), key=lambda pair: pair[0])
        if not rosters:
            rs._regiment_layout_cache = []
            return

        active_regiment_entities: set[int] = set()
        for _, roster in rosters:
            active_regiment_entities.update(roster.regiment_entities)
        sprites.cleanup_regiment_sprites(active_regiment_entities)

        board_left = ctx.board_left
        board_right = ctx.board_right
        board_top = ctx.board_top
        total_width = board_right - board_left
        window_w = ctx.window_width
        left_space = max(0, board_left - SIDE_GAP)
        right_space = max(0, (window_w - board_right) - SIDE_GAP)
        left_col_w = max(SIDE_PANEL_MIN_WIDTH, left_space)
        right_col_w = max(SIDE_PANEL_MIN_WIDTH, right_space)
        left_panel_left = board_left - SIDE_GAP - left_col_w
        right_panel_left = board_right + SIDE_GAP
        left_panel_center = left_panel_left + left_col_w / 2
        right_panel_center = right_panel_left + right_col_w / 2

        # New layout: For each player: two vertically stacked inactive units adjacent to a large active unit.
        # Horizontal ordering overall (L->R): blank | P1 inactive stack | P1 active | spacer | P2 active | P2 inactive stack | blank
        # If fewer than two inactive units, show only available. If more than two, take first two by slot order.
        base_radius = 40  # larger inactive circles
        active_radius = 70  # larger active circle
        outline_color = (245, 245, 245)
        # Shift active units more toward center for breathing room
        p1_active_x = board_left + total_width * 0.35
        p2_active_x = board_right - total_width * 0.35
        inactive_stack_dx = 140  # increased horizontal separation from active circle
        p1_stack_x = p1_active_x - inactive_stack_dx
        p2_stack_x = p2_active_x + inactive_stack_dx
        active_center_y = board_top + 145  # move active slightly up
        stack_top_y = board_top + 190     # move top inactive further up
        stack_bottom_y = board_top + 75  # wider vertical gap
        text_commands: list[tuple[str, float, float, tuple[int, int, int], int]] = []
        layout_cache = []

        for index, (owner_entity, roster) in enumerate(rosters):
            if not roster.regiment_entities:
                continue
            is_first_player = index == 0
            active_x = p1_active_x if is_first_player else p2_active_x
            stack_x = p1_stack_x if is_first_player else p2_stack_x
            # Collect inactive slots (exclude active_index)
            inactive_slots = [s for s in range(len(roster.regiment_entities)) if s != roster.active_index]
            # Limit to two for display
            display_inactive = inactive_slots[:2]
            position_by_slot: dict[int, tuple[float, float, float]] = {}
            # Active regiment placement
            position_by_slot[roster.active_index] = (active_x, active_center_y, active_radius)
            # Inactive stack placement (top then bottom)
            for pos_idx, slot in enumerate(display_inactive):
                # If only one inactive, center it vertically between stack positions
                if len(display_inactive) == 1:
                    cy = (stack_top_y + stack_bottom_y) / 2
                else:
                    cy = stack_top_y if pos_idx == 0 else stack_bottom_y
                position_by_slot[slot] = (stack_x, cy, base_radius)

            for slot, regiment_entity in enumerate(roster.regiment_entities):
                coords = position_by_slot.get(slot)
                if coords is None:
                    continue
                center_x, center_y, radius = coords
                try:
                    regiment: Regiment = rs.world.component_for_entity(regiment_entity, Regiment)
                except KeyError:
                    continue

                try:
                    fill_color = registry.background_for(regiment.unit_type)
                except KeyError:
                    fill_color = (180, 180, 180)

                can_attack = (
                    rs._current_active_owner is not None and
                    owner_entity == rs._current_active_owner and
                    slot == roster.active_index and
                    regiment.battle_readiness >= rs._attack_threshold
                )
                if can_attack:
                    pulse = (math.sin(rs._time * 3.0) + 1.0) * 0.5
                    glow_radius = radius + 10 + pulse * 6
                    glow_alpha = int(80 + pulse * 100)
                    glow_color = (90, 255, 150, glow_alpha)
                    arcade.draw_circle_filled(center_x, center_y, glow_radius, glow_color)
                arcade.draw_circle_filled(center_x, center_y, radius, fill_color)
                outline_thickness = 4 if slot == roster.active_index else 2
                arcade.draw_circle_outline(center_x, center_y, radius + outline_thickness, outline_color, outline_thickness)

                sprite = sprites.ensure_regiment_sprite(arcade, regiment_entity, regiment.unit_type)
                if sprite is not None:
                    icon_size = radius * 1.6
                    sprites.update_sprite_visuals(sprite, center_x, center_y, icon_size, 255)
                layout_cache.append({
                    "owner_entity": owner_entity,
                    "regiment_entity": regiment_entity,
                    "center_x": center_x,
                    "center_y": center_y,
                    "radius": radius,
                    "is_active": slot == roster.active_index,
                })

                # Text layout adjustments: active unit keeps vertical placement; non-active units show side text.
                morale_text = f"Mor {regiment.morale:.0f}"  # shortened label for compactness
                readiness_text = f"R {regiment.battle_readiness}"  # shortened label
                if slot == roster.active_index:
                    # Active: morale above, readiness below
                    text_commands.append((morale_text, center_x, center_y + radius + 20, (240, 240, 240), 13))
                    text_commands.append((readiness_text, center_x, center_y - radius - 32, (230, 230, 230), 12))
                else:
                    # Non-active: stack morale above readiness on side: left for player 1, right for player 2
                    side_offset = radius + 50
                    if is_first_player:
                        mx = center_x - side_offset
                    else:
                        mx = center_x + side_offset
                    text_commands.append((morale_text, mx, center_y + 10, (240, 240, 240), 11))
                    text_commands.append((readiness_text, mx, center_y - 12, (230, 230, 230), 11))

        rs._regiment_layout_cache = layout_cache

        sprites.draw_regiment_sprites()

        for text, x, y, color_val, font_size in text_commands:
            arcade.draw_text(text, x, y, color_val, font_size, anchor_x="center")

    def hit_test(self, x: float, y: float):
        cache = getattr(self._rs, "_regiment_layout_cache", None)
        if not cache:
            return None
        for entry in cache:
            dx = x - entry["center_x"]
            dy = y - entry["center_y"]
            if dx * dx + dy * dy <= entry["radius"] * entry["radius"]:
                return entry
        return None
