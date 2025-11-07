from pathlib import Path

from ecs.events.bus import (EVENT_TICK, EventBus, EVENT_TILE_SELECTED, EVENT_TILE_DESELECTED,
                            EVENT_MATCH_FOUND, EVENT_MATCH_CLEARED,
                            EVENT_TILE_SWAP_REQUEST, EVENT_TILE_SWAP_FINALIZE)
from ecs.components.active_switch import ActiveSwitch
from ecs.components.tile_type_registry import TileTypeRegistry
from ecs.components.tile_types import TileTypes
from ecs.components.tile import TileType
from ecs.components.board_position import BoardPosition
from ecs.components.animation_swap import SwapAnimation
from ecs.components.animation_fall import FallAnimation
from ecs.components.animation_refill import RefillAnimation
from ecs.components.animation_fade import FadeAnimation
from ecs.components.tile_bank import TileBank
# Removed legacy NAME_TO_COLOR; colors resolved via TileTypes registry only.
from ecs.constants import GRID_ROWS, GRID_COLS, TILE_SIZE, BOTTOM_MARGIN
from esper import World

PADDING = 4

class RenderSystem:
    def __init__(self, world: World, event_bus: EventBus, window):
        self.world = world
        self.event_bus = event_bus
        self.window = window
        self.event_bus.subscribe(EVENT_TICK, self.on_tick)
        self.event_bus.subscribe(EVENT_TILE_SELECTED, self.on_tile_selected)
        self.event_bus.subscribe(EVENT_TILE_DESELECTED, self.on_tile_deselected)
        self.event_bus.subscribe(EVENT_MATCH_FOUND, self.on_match_found)
        self.event_bus.subscribe(EVENT_MATCH_CLEARED, self.on_match_cleared)
        self.event_bus.subscribe(EVENT_TILE_SWAP_REQUEST, self.on_swap_request)
        self.event_bus.subscribe(EVENT_TILE_SWAP_FINALIZE, self.on_swap_finalize)
        self.selected = None
        self._tile_size = TILE_SIZE  # dynamic scaling; updated on resize/process
        self._last_window_size = (self.window.width, self.window.height)
        self.use_easing = True
        self._texture_dir = Path(__file__).resolve().parents[3] / "graphics"
        self._entity_sprite_map = {}  # entity id -> arcade.Sprite
        self._icon_sprites = None     # arcade.SpriteList (lazy)

    def notify_resize(self, width: int, height: int):
        self._last_window_size = (width, height)
        self._recalculate_tile_size()

    def _recalculate_tile_size(self):
        # Reserve side panels for abilities (two columns) and margins; compute max tile size fitting remaining width/height.
        ability_panel_w = 160  # base design; can also scale slightly if very wide.
        side_reserve = ability_panel_w * 2 + 120  # include padding/margins
        available_w = max(200, self.window.width - side_reserve)
        # Vertical reserve: top/bottom margins and space for banks/ability labels (~260px design)
        vertical_reserve = BOTTOM_MARGIN + 260
        available_h = max(200, self.window.height - vertical_reserve)
        tile_by_w = available_w / GRID_COLS
        tile_by_h = available_h / GRID_ROWS
        self._tile_size = int(min(tile_by_w, tile_by_h))
        if self._tile_size < 20:
            self._tile_size = 20  # safety minimum

    def on_tick(self, sender, **kwargs):
        # Rendering currently happens only in window.on_draw calling process()
        # Could move incremental animation easing prep here later.
        return

    def on_tile_selected(self, sender, **kwargs):
        self.selected = (kwargs.get('row'), kwargs.get('col'))

    def on_tile_deselected(self, sender, **kwargs):
        # Optionally keep previous position for future fade-out; currently just clear.
        self.selected = None
        self.last_deselected = (kwargs.get('prev_row'), kwargs.get('prev_col')) if 'prev_row' in kwargs else None

    # Swap lifecycle visuals handled implicitly via SwapAnimation component; no direct handlers needed.

    def process(self):
    # Background cleared by Arcade window prior to on_draw.
    # Local import keeps tests headless without creating a window.
        import arcade
        # Headless safeguard: if no active Arcade window (unit tests), skip actual draw calls but still build layout cache.
        headless = False
        try:
            arcade.get_window()
        except Exception:
            headless = True
    # Recalculate tile size if window size changed.
        if (self.window.width, self.window.height) != self._last_window_size:
            self._last_window_size = (self.window.width, self.window.height)
            self._recalculate_tile_size()
        tile_size = self._tile_size
        total_width = GRID_COLS * tile_size
        start_x = (self.window.width - total_width) / 2
        start_y = BOTTOM_MARGIN
    # Precompute cell centers for animation interpolation.
        positions = {}
        for ent, pos in self.world.get_component(BoardPosition):
            cx = start_x + pos.col * tile_size + tile_size/2
            cy = start_y + pos.row * tile_size + tile_size/2
            positions[(pos.row, pos.col)] = (ent, cx, cy)

        outline_commands = []
        active_entities = {details[0] for details in positions.values()}
        if not headless:
            self._cleanup_missing_sprites(active_entities)
        registry = self._registry()
        for (row, col), (ent, base_x, base_y) in positions.items():
            try:
                sw: ActiveSwitch = self.world.component_for_entity(ent, ActiveSwitch)
            except KeyError:
                continue
            tile_active = sw.active
            tile_type_name = None
            if tile_active:
                try:
                    tt: TileType = self.world.component_for_entity(ent, TileType)
                    tile_type_name = tt.type_name
                except KeyError:
                    tile_type_name = None
            color = registry.background_for(tile_type_name) if (tile_active and tile_type_name) else None
            alpha_override = None
            draw_x, draw_y = base_x, base_y
            # Animation interpolation (swap / fall / refill). Each component is independent.
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
            # Fall animation
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
                    # Interpolate both axes so vertical motion is visible
                    draw_x = from_pos[0] + (to_pos[0] - from_pos[0]) * p
                    draw_y = from_pos[1] + (to_pos[1] - from_pos[1]) * p
            # Refill (spawn) animation
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
            # Fade overlay alpha (tile already logically cleared elsewhere)
            if color is None:
                for _, fade in self.world.get_component(FadeAnimation):
                    if fade.pos == (row, col):
                        color = (80, 80, 80)
                        alpha_override = fade.alpha
                        break
                if color is None:
                    if not headless:
                        self._remove_entity_sprite(ent)
                    continue
            if not tile_active and not headless:
                self._remove_entity_sprite(ent)
            draw_size = max(tile_size - PADDING, 4)
            radius = draw_size / 2
            # Store draw coordinates for tests/headless verification
            if not hasattr(self, '_last_draw_coords'):
                self._last_draw_coords = {}
            self._last_draw_coords[(row, col)] = (draw_x, draw_y)
            if headless:
                continue
            if alpha_override is not None and hasattr(arcade, 'draw_circle_filled'):
                r, g, b = color
                arcade.draw_circle_filled(draw_x, draw_y, radius, (r, g, b, int(255 * alpha_override)))
            else:
                arcade.draw_circle_filled(draw_x, draw_y, radius, color)
            sprite = None
            if tile_active and tile_type_name:
                sprite = self._ensure_entity_sprite(arcade, ent, tile_type_name)
            if sprite is not None:
                icon_alpha = int(255 * alpha_override) if alpha_override is not None else 255
                icon_size = draw_size * 0.78
                self._update_sprite_visuals(sprite, draw_x, draw_y, icon_size, icon_alpha, tint_color=color)
            if self.selected and (row, col) == self.selected:
                outline_commands.append((draw_x, draw_y, radius + 3))
        if not headless and self._icon_sprites is not None:
            self._icon_sprites.draw()
        for draw_x, draw_y, outline_radius in outline_commands:
            arcade.draw_circle_outline(draw_x, draw_y, outline_radius, (255, 255, 255), 3)
        # Tile bank overlays for all owners (left for first, right for second)
        if not headless:
            banks = list(self.world.get_component(TileBank))
            # Sort banks by owner_entity for deterministic ordering
            banks_sorted = sorted(banks, key=lambda pair: pair[1].owner_entity)
            overlay_y = self.window.height - 30
            line_h = 16
            total_width = GRID_COLS * TILE_SIZE
            board_left = (self.window.width - total_width) / 2
            board_right = board_left + total_width
            for idx, (bank_ent, bank) in enumerate(banks_sorted):
                items = sorted(bank.counts.items(), key=lambda kv: (-kv[1], kv[0]))
                if idx == 0:
                    overlay_x = 16
                    title = "P1 Bank"
                else:
                    overlay_x = board_right + 40  # right side offset
                    title = f"P{idx+1} Bank"
                arcade.draw_text(title, overlay_x, overlay_y, arcade.color.WHITE, 12)
                for i, (type_name, count) in enumerate(items):
                    try:
                        color_tuple = registry.background_for(type_name)
                    except Exception:
                        color_tuple = None
                    if color_tuple is None:
                        parts = type_name.split('_')
                        if len(parts) == 3 and all(p.isdigit() for p in parts):
                            r, g, b = map(int, parts)
                            color_tuple = (r, g, b)
                    swatch_x = overlay_x
                    swatch_y = overlay_y - (i+1)*line_h - 4
                    swatch_cx = swatch_x + 16
                    swatch_cy = swatch_y + 8
                    if color_tuple:
                        arcade.draw_circle_filled(swatch_cx, swatch_cy, 7, color_tuple)
                    else:
                        arcade.draw_circle_outline(swatch_cx, swatch_cy, 7, arcade.color.WHITE, 1)
                    arcade.draw_text(f"{type_name}: {count}", swatch_x + 28, swatch_y + 2, arcade.color.WHITE, 12)

        # Ability column (left side stacked rectangles)
        self._render_abilities(arcade, headless=headless)

    def _cleanup_missing_sprites(self, active_entities: set[int]) -> None:
        if not self._entity_sprite_map:
            return
        stale_entities = [ent for ent in self._entity_sprite_map.keys() if ent not in active_entities]
        for ent in stale_entities:
            self._remove_entity_sprite(ent)

    def _ensure_entity_sprite(self, arcade_module, entity: int, type_name: str):
        if not type_name:
            return None
        if self._icon_sprites is None:
            self._icon_sprites = arcade_module.SpriteList()
        sprite = self._entity_sprite_map.get(entity)
        current_type = getattr(sprite, "_tile_type_name", None) if sprite is not None else None
        if sprite is not None and current_type != type_name:
            self._remove_entity_sprite(entity)
            sprite = None
        if sprite is None:
            sprite = self._create_tile_sprite(arcade_module, type_name)
            if sprite is None:
                return None
            sprite._tile_type_name = type_name  # type: ignore[attr-defined]
            self._entity_sprite_map[entity] = sprite
            self._icon_sprites.append(sprite)
        return sprite

    def _create_tile_sprite(self, arcade_module, type_name: str):
        texture_path = self._texture_dir / f"{type_name}.png"
        if not texture_path.exists():
            return None
        try:
            sprite = arcade_module.Sprite(str(texture_path))
        except Exception:
            return None
        sprite._tile_type_name = type_name  # type: ignore[attr-defined]
        return sprite

    def _update_sprite_visuals(self, sprite, center_x: float, center_y: float, icon_size: float, alpha: int, tint_color=None) -> None:
        sprite.center_x = center_x
        sprite.center_y = center_y
        texture = sprite.texture
        if texture and texture.width and texture.height:
            max_dim = max(texture.width, texture.height)
            if max_dim:
                sprite.scale = icon_size / max_dim
        sprite.alpha = max(0, min(255, int(alpha)))
        if tint_color is not None and hasattr(sprite, 'color') and isinstance(tint_color, tuple):
            # Arcade expects RGB (ignores alpha here)
            r,g,b = tint_color[:3]
            sprite.color = (r,g,b)

    def _remove_entity_sprite(self, entity: int) -> None:
        sprite = self._entity_sprite_map.pop(entity, None)
        if sprite is not None:
            sprite.remove_from_sprite_lists()

    def _render_abilities(self, arcade, headless: bool = False):
        """Render abilities as stacked rectangles left of board.

        Layout:
          - Fixed width panel near left edge (or left margin) separate from bank.
          - Each ability: rectangle with name and cost line(s).
          - Background color indicates affordability: green if bank covers all costs, red if not.
        """
        # Imports placed here to avoid issues during test collection if Arcade context not initialized.
        from ecs.components.ability import Ability
        ability_comps = list(self.world.get_component(Ability))
        if not ability_comps:
            return
        # Resolve tile bank for affordability
        # Group abilities by owner (multi-player support)
        from ecs.components.ability_list_owner import AbilityListOwner
        owners = list(self.world.get_component(AbilityListOwner))
        # Build cache list per owner
        self._ability_layout_cache = []
        from ecs.ui.ability_layout import compute_ability_layout
        rect_w = 160
        rect_h = 52
        spacing = 8
        base_top = self.window.height - 240
        tile_size = self._tile_size
        total_width = GRID_COLS * tile_size
        board_left = (self.window.width - total_width) / 2
        board_right = board_left + total_width
        left_panel_x = board_left - (rect_w + 24)
        right_panel_x = board_right + 24
        # Map owner -> bank counts
        banks = {bank.owner_entity: bank.counts for _, bank in self.world.get_component(TileBank)}
        for col_index, (owner_ent, owner_comp) in enumerate(owners):
            owner_abilities = [(ent, ability) for (ent, ability) in ability_comps if ent in owner_comp.ability_entities]
            counts = banks.get(owner_ent, {})
            panel_x = left_panel_x if col_index == 0 else right_panel_x
            layout_entries = compute_ability_layout(
                owner_abilities,
                counts,
                owner_entity=owner_ent,
                start_x=panel_x,
                start_top=base_top,
                rect_w=rect_w,
                rect_h=rect_h,
                spacing=spacing,
            )
            self._ability_layout_cache.extend(layout_entries)
        import arcade
        # Determine currently targeting ability (if any) and active owner
        targeting_ability_entity = None
        active_owner = None
        try:
            from ecs.components.targeting_state import TargetingState
            targeting_states = list(self.world.get_component(TargetingState))
            if targeting_states:
                targeting_ability_entity = targeting_states[0][1].ability_entity
            from ecs.components.active_turn import ActiveTurn
            active_list = list(self.world.get_component(ActiveTurn))
            if active_list:
                active_owner = active_list[0][1].owner_entity
        except Exception:
            targeting_ability_entity = None
            active_owner = None
        # Mark targeting flag in layout cache
        for entry in self._ability_layout_cache:
            entry['is_targeting'] = (targeting_ability_entity is not None and entry['entity'] == targeting_ability_entity)
            entry['is_active'] = (active_owner is not None and entry['owner_entity'] == active_owner)
        for entry in self._ability_layout_cache:
            x = entry['x']; y = entry['y']; w = entry['width']; h = entry['height']
            affordable = entry['affordable']
            # Slightly brighten active owner's background
            base_color = (40, 100, 40) if affordable else (120, 40, 40)
            if entry['is_active'] and not entry['is_targeting']:
                r,g,b = base_color
                bg_color = (min(255, r+30), min(255, g+30), min(255, b+30))
            else:
                bg_color = base_color
            border_color = (200, 200, 200)
            points = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            if headless:
                # Skip drawing; flags still updated.
                continue
            if hasattr(arcade, 'draw_polygon_filled'):
                # If targeting, tint background lighter and outline blue
                if entry['is_targeting']:
                    arcade.draw_polygon_filled(points, (70, 130, 180))  # steel-ish base
                else:
                    arcade.draw_polygon_filled(points, bg_color)
                if hasattr(arcade, 'draw_polygon_outline'):
                    if entry['is_targeting']:
                        arcade.draw_polygon_outline(points, arcade.color.LIGHT_BLUE, 3)
                    elif entry['is_active']:
                        arcade.draw_polygon_outline(points, (150, 200, 255), 2)
                    else:
                        arcade.draw_polygon_outline(points, border_color, 2)
            else:
                arcade.draw_circle_filled(x + w/2, y + h/2, w/2, bg_color)
                arcade.draw_circle_outline(x + w/2, y + h/2, w/2, border_color, 2)
            name_y = y + h - 16
            arcade.draw_text(entry['name'], x + 8, name_y, arcade.color.WHITE, 14)
            # Show only required costs (omit available amount)
            cost_line = " ".join(f"{ctype}:{cval}" for ctype, cval in entry['cost'].items())
            arcade.draw_text(cost_line, x + 8, y + 8, arcade.color.WHITE, 12)

    def get_ability_at_point(self, x: float, y: float):
        """Return ability layout entry if point inside its rectangle."""
        if not hasattr(self, '_ability_layout_cache'):
            return None
        for entry in self._ability_layout_cache:
            ex, ey, w, h = entry['x'], entry['y'], entry['width'], entry['height']
            if ex <= x <= ex + w and ey <= y <= ey + h:
                return entry
        return None
    def on_match_found(self, sender, **kwargs):
        # Notification only; no immediate action required.
        return

    def on_animation_start(self, sender, **kwargs):
        return

    def on_match_cleared(self, sender, **kwargs):
        return

    def on_swap_request(self, sender, **kwargs):
        # Clear selection immediately when a swap begins
        self.selected = None

    def on_swap_finalize(self, sender, **kwargs):
        # Ensure selection cleared after swap completes
        self.selected = None

    # Removed specific gravity animation handlers; handled by generic on_animation_start
    def _get_entity_at(self, row: int, col: int):
        for ent, pos in self.world.get_component(BoardPosition):
            if pos.row == row and pos.col == col:
                return ent
        return None

    def on_refill_completed(self, sender, **kwargs):
        return

    def _registry(self) -> TileTypes:
        for ent, _ in self.world.get_component(TileTypeRegistry):
            return self.world.component_for_entity(ent, TileTypes)
        raise RuntimeError('TileTypes definitions not found')

