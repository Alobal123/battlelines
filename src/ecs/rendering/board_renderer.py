from __future__ import annotations

from typing import TYPE_CHECKING

from ecs.components.active_switch import ActiveSwitch
from ecs.components.tile import TileType
from ecs.components.tile_status_overlay import TileStatusOverlay

if TYPE_CHECKING:
    from ecs.components.tile_types import TileTypes
    from ecs.rendering.context import RenderContext
    from ecs.rendering.sprite_cache import SpriteCache
    from ecs.systems.render import RenderSystem


class BoardRenderer:
    def __init__(self, render_system: RenderSystem, sprite_cache: "SpriteCache", padding: int = 4):
        self._rs = render_system
        self._sprites = sprite_cache
        self._padding = padding

    def render(self, arcade, ctx: RenderContext, registry: TileTypes, headless: bool) -> None:
        rs = self._rs
        sprites = self._sprites
        positions = ctx.board_positions
        outline_commands: list[tuple[float, float, float]] = []
        active_entities = {details[0] for details in positions.values()}
        if not headless:
            sprites.cleanup_tile_sprites(active_entities)

        rs._last_tile_layout = {}
        rs._last_draw_coords = {}

        for (row, col), (ent, base_x, base_y) in positions.items():
            try:
                switch = rs.world.component_for_entity(ent, ActiveSwitch)
            except KeyError:
                continue
            tile_active = switch.active
            overlay: TileStatusOverlay | None
            try:
                overlay = rs.world.component_for_entity(ent, TileStatusOverlay)
            except KeyError:
                overlay = None
            tile_type_name = None
            if tile_active:
                try:
                    tile_component: TileType = rs.world.component_for_entity(ent, TileType)
                    tile_type_name = tile_component.type_name
                except KeyError:
                    tile_type_name = None
            color = registry.background_for(tile_type_name) if tile_active and tile_type_name else None
            alpha_override = None
            draw_x = base_x
            draw_y = base_y

            swap_anim = ctx.swap_by_pos.get((row, col))
            if swap_anim is not None:
                src_pos = positions[swap_anim.src][1:]
                dst_pos = positions[swap_anim.dst][1:]
                p = swap_anim.progress
                if (row, col) == swap_anim.src:
                    draw_x = src_pos[0] + (dst_pos[0] - src_pos[0]) * p
                    draw_y = src_pos[1] + (dst_pos[1] - src_pos[1]) * p
                else:
                    draw_x = dst_pos[0] + (src_pos[0] - dst_pos[0]) * p
                    draw_y = dst_pos[1] + (src_pos[1] - dst_pos[1]) * p

            fall_anim = ctx.fall_by_dst.get((row, col))
            if fall_anim is not None:
                from_pos = positions[fall_anim.src][1:]
                to_pos = positions[fall_anim.dst][1:]
                p_lin = fall_anim.linear
                p = p_lin
                if rs.use_easing:
                    if p < 0.5:
                        p = 2 * p * p
                    else:
                        p = -2 * p * p + 4 * p - 1
                draw_x = from_pos[0] + (to_pos[0] - from_pos[0]) * p
                draw_y = from_pos[1] + (to_pos[1] - from_pos[1]) * p

            refill_anim = ctx.refill_by_pos.get((row, col))
            if refill_anim is not None:
                to_pos = positions[(row, col)][1:]
                start_y2 = to_pos[1] + ctx.tile_size * 1.2
                p_lin = refill_anim.linear
                p = p_lin
                if rs.use_easing:
                    if p < 0.5:
                        p = 2 * p * p
                    else:
                        p = -2 * p * p + 4 * p - 1
                draw_y = start_y2 + (to_pos[1] - start_y2) * p

            if color is None:
                fade_anim = ctx.fade_by_pos.get((row, col))
                if fade_anim is not None:
                    color = (80, 80, 80)
                    alpha_override = fade_anim.alpha
                if color is None:
                    if not headless:
                        sprites.remove_tile_sprite(ent)
                    continue

            if not tile_active and not headless:
                sprites.remove_tile_sprite(ent)

            draw_size = max(ctx.tile_size - self._padding, 4)
            radius = draw_size / 2
            rs._last_tile_layout[(row, col)] = {
                "entity": ent,
                "center": (draw_x, draw_y),
                "radius": radius,
            }
            rs._last_draw_coords[(row, col)] = (draw_x, draw_y)
            if headless:
                continue

            if alpha_override is not None and hasattr(arcade, "draw_circle_filled"):
                r, g, b = color
                arcade.draw_circle_filled(draw_x, draw_y, radius, (r, g, b, int(255 * alpha_override)))
            else:
                arcade.draw_circle_filled(draw_x, draw_y, radius, color)

            sprite = None
            if tile_active and tile_type_name:
                sprite = sprites.ensure_tile_sprite(arcade, ent, tile_type_name)
            if sprite is not None:
                icon_alpha = int(255 * alpha_override) if alpha_override is not None else 255
                icon_size = draw_size * 0.78
                sprites.update_sprite_visuals(sprite, draw_x, draw_y, icon_size, icon_alpha, tint_color=color)

            if overlay is not None and overlay.tint is not None:
                or_, og, ob = overlay.tint
                overlay_fill = (or_, og, ob, 72)
                overlay_outline = (or_, og, ob, 200)
                arcade.draw_circle_filled(draw_x, draw_y, radius * 0.92, overlay_fill)
                arcade.draw_circle_outline(draw_x, draw_y, radius, overlay_outline, 3)

            if rs.selected and (row, col) == rs.selected:
                outline_commands.append((draw_x, draw_y, radius + 3))

        if not headless:
            sprites.draw_tile_sprites()
        for draw_x, draw_y, outline_radius in outline_commands:
            arcade.draw_circle_outline(draw_x, draw_y, outline_radius, (255, 255, 255), 3)
