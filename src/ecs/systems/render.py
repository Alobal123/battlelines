from ecs.events.bus import (EVENT_TICK, EventBus, EVENT_TILE_SELECTED,
                            EVENT_MATCH_FOUND, EVENT_MATCH_CLEARED)
from ecs.components.tile import TileColor
from ecs.components.board_position import BoardPosition
from ecs.components.animation_swap import SwapAnimation
from ecs.components.animation_fall import FallAnimation
from ecs.components.animation_refill import RefillAnimation
from ecs.components.animation_fade import FadeAnimation
from ecs.constants import GRID_ROWS, GRID_COLS, TILE_SIZE, BOTTOM_MARGIN
from esper import World
import arcade

PADDING = 4

class RenderSystem:
    def __init__(self, world: World, event_bus: EventBus, window):
        self.world = world
        self.event_bus = event_bus
        self.window = window
        self.event_bus.subscribe(EVENT_TICK, self.on_tick)
        self.event_bus.subscribe(EVENT_TILE_SELECTED, self.on_tile_selected)
        self.event_bus.subscribe(EVENT_MATCH_FOUND, self.on_match_found)
        self.event_bus.subscribe(EVENT_MATCH_CLEARED, self.on_match_cleared)
        self.selected = None
        self.use_easing = True

    def on_tick(self, sender, **kwargs):
        pass

    def on_tile_selected(self, sender, **kwargs):
        self.selected = (kwargs.get('row'), kwargs.get('col'))

    def on_swap_request(self, sender, **kwargs):
        pass

    def on_swap_valid(self, sender, **kwargs):
        pass

    def on_swap_invalid(self, sender, **kwargs):
        pass

    def on_swap_finalize(self, sender, **kwargs):
        pass

    def process(self):
        # Background already cleared in window.on_draw
        # Compute grid origin (bottom-center) using left/bottom corner
        total_width = GRID_COLS * TILE_SIZE
        start_x = (self.window.width - total_width) / 2
        start_y = BOTTOM_MARGIN
        # Precompute positions for animation interpolation
        positions = {}
        for ent, pos in self.world.get_component(BoardPosition):
            cx = start_x + pos.col * TILE_SIZE + TILE_SIZE/2
            cy = start_y + pos.row * TILE_SIZE + TILE_SIZE/2
            positions[(pos.row, pos.col)] = (ent, cx, cy)

        # Draw tiles (with animation if active swap)
        for (row, col), (ent, base_x, base_y) in positions.items():
            color_comp = self.world.component_for_entity(ent, TileColor)
            color = color_comp.color
            alpha_override = None
            # If cleared, we may find a fading copy from Animations component later
            if color is None:
                pass
            draw_x, draw_y = base_x, base_y
            # Animation data now lives in Animations component; we derive positions via component.
            # Swap interpolation
            for _, swap in self.world.get_component(SwapAnimation):
                if (row, col) == swap.src or (row, col) == swap.dst:
                    src_pos = positions[swap.src][1:]
                    dst_pos = positions[swap.dst][1:]
                    p = swap.progress
                    if (row, col) == swap.src:
                        draw_x = src_pos[0] + (dst_pos[0] - src_pos[0]) * p
                        draw_y = src_pos[1] + (dst_pos[1] - src_pos[1]) * p
                    else:
                        draw_x = dst_pos[0] + (src_pos[0] - dst_pos[0]) * p
                        draw_y = dst_pos[1] + (src_pos[1] - dst_pos[1]) * p
            # Falling animations
            for _, fall in self.world.get_component(FallAnimation):
                if fall.dst == (row, col):
                    from_pos = positions[fall.src][1:]
                    to_pos = positions[fall.dst][1:]
                    p_lin = fall.linear
                    p = p_lin
                    if self.use_easing:
                        if p < 0.5:
                            p = 2 * p * p
                        else:
                            p = -2 * p * p + 4 * p -1
                    draw_x = from_pos[0] + (to_pos[0] - from_pos[0]) * p
                    draw_y = from_pos[1] + (to_pos[1] - from_pos[1]) * p
            # Refill spawn animations
            for _, ref_anim in self.world.get_component(RefillAnimation):
                if ref_anim.pos == (row, col):
                    to_pos = positions[(row, col)][1:]
                    start_y2 = to_pos[1] + TILE_SIZE * 1.2
                    p_lin = ref_anim.linear
                    p = p_lin
                    if self.use_easing:
                        if p < 0.5:
                            p = 2 * p * p
                        else:
                            p = -2 * p * p + 4 * p -1
                    draw_y = start_y2 + (to_pos[1] - start_y2) * p
            # Fade overlay if tile cleared
            if color is None:
                for _, fade in self.world.get_component(FadeAnimation):
                    if fade.pos == (row, col):
                        # Use previous color snapshot? We rely on TileColor color before it became None; could store separately.
                        # For now skip if no color.
                        color = (80,80,80)  # fallback tint
                        alpha_override = fade.alpha
                        break
                if color is None:
                    continue
            if color is None:
                continue
            radius = (TILE_SIZE - PADDING) / 2
            if alpha_override is not None and hasattr(arcade, 'draw_circle_filled'):  # alpha blend
                r,g,b = color
                arcade.draw_circle_filled(draw_x, draw_y, radius, (r, g, b, int(255*alpha_override)))
            else:
                arcade.draw_circle_filled(draw_x, draw_y, radius, color)
            if self.selected and (row, col) == self.selected:
                arcade.draw_circle_outline(draw_x, draw_y, radius, (255,255,255), 3)
    def on_match_found(self, sender, **kwargs):
        # Pure notification; setup occurs on CLEAR_BEGIN
        pass

    def on_animation_start(self, sender, **kwargs):
        pass

    def on_match_cleared(self, sender, **kwargs):
        # Nothing extra; fading list already set
        pass

    # Removed specific gravity animation handlers; handled by generic on_animation_start
    def _get_entity_at(self, row: int, col: int):
        for ent, pos in self.world.get_component(BoardPosition):
            if pos.row == row and pos.col == col:
                return ent
        return None

    def on_refill_completed(self, sender, **kwargs):
        pass

