from pathlib import Path
from typing import Any
import math

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
from ecs.components.regiment import Regiment
from ecs.components.army_roster import ArmyRoster
from ecs.components.active_turn import ActiveTurn
from ecs.systems.battle import BattleConfig
# Removed legacy NAME_TO_COLOR; colors resolved via TileTypes registry only.
from ecs.constants import (
    GRID_ROWS, GRID_COLS, TILE_SIZE, BOTTOM_MARGIN,
    BOARD_MAX_WIDTH_PCT, BOARD_MAX_HEIGHT_PCT,
    SIDE_PANEL_MIN_WIDTH, SIDE_GAP, BANK_BAR_HEIGHT, ABILITY_TOP_PADDING, SIDE_PANEL_INNER_PAD,
)
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
        # Cache for smoothed textures (path,max_dim)->arcade.Texture
        self._smoothed_texture_cache = {}
        # Bank row sprites keyed by (bank_entity, type_name) so each player can display same type concurrently
        self._bank_row_sprite_map: dict[tuple[int, str], Any] = {}
        self._bank_icon_sprites = None  # arcade.SpriteList
        # Regiment badge sprites keyed by regiment entity id
        self._regiment_sprite_map: dict[int, Any] = {}
        self._regiment_sprites = None  # arcade.SpriteList
        self._regiment_layout_cache = []
        self._time = 0.0
        self._attack_threshold = BattleConfig().minimum_readiness_to_attack
        self._current_active_owner: int | None = None

    def notify_resize(self, width: int, height: int):
        self._last_window_size = (width, height)
        self._recalculate_tile_size()

    def _recalculate_tile_size(self):
        # Percentage-based sizing: board may not exceed configured fraction of window.
        max_board_w = self.window.width * BOARD_MAX_WIDTH_PCT
        max_board_h = (self.window.height - BOTTOM_MARGIN) * BOARD_MAX_HEIGHT_PCT
        tile_by_w = max_board_w / GRID_COLS
        tile_by_h = max_board_h / GRID_ROWS
        self._tile_size = int(min(tile_by_w, tile_by_h))
        if self._tile_size < 20:
            self._tile_size = 20  # safety minimum

    def on_tick(self, sender, **kwargs):
        # Rendering currently happens only in window.on_draw calling process()
        # Could move incremental animation easing prep here later.
        dt = kwargs.get('dt', 1/60)
        try:
            self._time += float(dt)
        except Exception:
            self._time += 1/60
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
        # Use computed tile size directly (shrink already accounted for via increased reserves)
        tile_size = self._tile_size
        total_width = GRID_COLS * tile_size
        start_x = (self.window.width - total_width) / 2
        start_y = BOTTOM_MARGIN
        board_left = start_x
        board_right = start_x + total_width
        board_top = start_y + GRID_ROWS * tile_size
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
        try:
            active_turn_entries = list(self.world.get_component(ActiveTurn))
            if active_turn_entries:
                self._current_active_owner = active_turn_entries[0][1].owner_entity
            else:
                self._current_active_owner = None
        except Exception:
            self._current_active_owner = None
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

        # Render side panels: horizontal bank bar above vertical abilities panel (both sides)
        if not headless:
            self._render_regiments(arcade, registry, board_left, board_right, board_top)
            self._render_side_panels(arcade, registry, start_y, tile_size)

        # Ability column rendering uses cached geometry prepared in side panel routine.
        self._render_abilities(arcade, headless=headless)

    # ------------------------------------------------------------------
    # Texture Smoothing Helper
    # ------------------------------------------------------------------
    def load_smoothed_texture(self, path: Path | str, max_dim: int | None = None):
        """Return a high-quality (optionally pre-resized) arcade.Texture.

        Uses Pillow LANCZOS (if available) to resize once, caching result.
        Subsequent calls reuse cached texture for the (path,max_dim) key.
        If max_dim is None, original image is loaded untouched.
        """
        import arcade  # local import keeps test environments light
        from PIL import Image
        if isinstance(path, Path):
            path = str(path)
        key = (path, max_dim)
        cached = self._smoothed_texture_cache.get(key)
        if cached is not None:
            return cached
        src_path = Path(path)
        if not src_path.exists():
            return None
        try:
            img = Image.open(src_path).convert("RGBA")
        except Exception:
            return None
        if max_dim is not None and max(img.size) > max_dim:
            w, h = img.size
            scale = max_dim / max(w, h)
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            resampling = getattr(Image, 'Resampling', None)
            if resampling and hasattr(resampling, 'LANCZOS'):
                img = img.resize((new_w, new_h), resampling.LANCZOS)
            else:
                img = img.resize((new_w, new_h))
        # Arcade can create a Texture directly from a PIL image via Texture.create
        try:
            texture = arcade.Texture(name=f"smooth:{src_path.name}:{max_dim}", image=img)
        except Exception:
            # Fallback: save to temp and load normally
            cache_file = src_path.parent / f"._smooth_cache_{src_path.stem}_{max_dim or 'orig'}.png"
            try:
                img.save(cache_file)
                texture = arcade.load_texture(cache_file)
            except Exception:
                return None
        self._smoothed_texture_cache[key] = texture
        return texture

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

    def _ensure_bank_row_sprite(self, arcade_module, bank_entity: int, type_name: str):
        """Ensure a cached sprite for a (bank_entity, type_name) pair.

        Previously we cached only per type_name, which prevented showing the same icon
        in both players' banks simultaneously. Now each bank gets its own sprite instance.
        """
        if not type_name:
            return None
        if self._bank_icon_sprites is None:
            self._bank_icon_sprites = arcade_module.SpriteList()
        key = (bank_entity, type_name)
        sprite = self._bank_row_sprite_map.get(key)
        if sprite is None:
            sprite = self._create_tile_sprite(arcade_module, type_name)
            if sprite is None:
                return None
            self._bank_row_sprite_map[key] = sprite
            self._bank_icon_sprites.append(sprite)
        return sprite

    def _ensure_regiment_sprite(self, arcade_module, entity: int, unit_type: str):
        if self._regiment_sprites is None:
            self._regiment_sprites = arcade_module.SpriteList()
        sprite = self._regiment_sprite_map.get(entity)
        current_type = getattr(sprite, "_unit_type", None) if sprite is not None else None
        if sprite is not None and current_type != unit_type:
            sprite.remove_from_sprite_lists()
            self._regiment_sprite_map.pop(entity, None)
            sprite = None
        if sprite is None:
            sprite = self._create_tile_sprite(arcade_module, unit_type)
            if sprite is None:
                return None
            sprite._unit_type = unit_type  # type: ignore[attr-defined]
            self._regiment_sprite_map[entity] = sprite
            self._regiment_sprites.append(sprite)
        return sprite

    def _cleanup_regiment_sprites(self, active_entities: set[int]) -> None:
        if not self._regiment_sprite_map:
            return
        stale = [ent for ent in self._regiment_sprite_map.keys() if ent not in active_entities]
        for ent in stale:
            sprite = self._regiment_sprite_map.pop(ent, None)
            if sprite is not None:
                sprite.remove_from_sprite_lists()

    def _create_tile_sprite(self, arcade_module, type_name: str):
        texture_path = self._texture_dir / f"{type_name}.png"
        if not texture_path.exists():
            return None
        # Use smoothed texture helper (limit icon max dimension for crisp UI)
        tex = self.load_smoothed_texture(texture_path, max_dim=96)
        if tex is None:
            return None
        try:
            sprite = arcade_module.Sprite()
            sprite.texture = tex
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
        """Render abilities as stacked rectangles inside the side panels.

        Geometry is computed each frame relative to board bounds.
        """
        from ecs.components.ability import Ability
        ability_comps = list(self.world.get_component(Ability))
        if not ability_comps:
            return
        from ecs.components.ability_list_owner import AbilityListOwner
        owners = list(self.world.get_component(AbilityListOwner))
        owners.sort(key=lambda item: item[0])
        from ecs.ui.ability_layout import compute_ability_layout
        rect_h = 52
        spacing = 8
        tile_size = self._tile_size
        total_width = GRID_COLS * tile_size
        board_left = (self.window.width - total_width) / 2
        board_right = board_left + total_width
        board_top = BOTTOM_MARGIN + GRID_ROWS * tile_size
        window_w = self.window.width
        left_space = max(0, board_left - SIDE_GAP)
        right_space = max(0, (window_w - board_right) - SIDE_GAP)
        left_col_w = max(SIDE_PANEL_MIN_WIDTH, left_space)
        right_col_w = max(SIDE_PANEL_MIN_WIDTH, right_space)
        # Ability panel top (just below bank bar)
        ability_panel_top = board_top - BANK_BAR_HEIGHT
        # We treat layout's start_top as the BOTTOM of the first rectangle (function naming legacy).
        # To keep a padding gap between bank bar and the first ability, subtract padding + rect height.
        first_rect_bottom = ability_panel_top - ABILITY_TOP_PADDING - rect_h
        # Width per side accounts for inner padding on both left/right.
        left_rect_w = max(60, left_col_w - 2 * SIDE_PANEL_INNER_PAD)
        right_rect_w = max(60, right_col_w - 2 * SIDE_PANEL_INNER_PAD)
        left_panel_x = board_left - SIDE_GAP - left_col_w + SIDE_PANEL_INNER_PAD
        right_panel_x = board_right + SIDE_GAP + SIDE_PANEL_INNER_PAD
        banks = {bank.owner_entity: bank.counts for _, bank in self.world.get_component(TileBank)}
        self._ability_layout_cache = []
        for col_index, (owner_ent, owner_comp) in enumerate(owners):
            owner_abilities = [(ent, ability) for (ent, ability) in ability_comps if ent in owner_comp.ability_entities]
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
            self._ability_layout_cache.extend(layout_entries)
        targeting_ability_entity = None
        try:
            from ecs.components.targeting_state import TargetingState
            targeting_states = list(self.world.get_component(TargetingState))
            if targeting_states:
                targeting_ability_entity = targeting_states[0][1].ability_entity
        except Exception:
            targeting_ability_entity = None
        for entry in self._ability_layout_cache:
            entry['is_targeting'] = (targeting_ability_entity is not None and entry['entity'] == targeting_ability_entity)
            entry['is_active'] = (self._current_active_owner is not None and entry['owner_entity'] == self._current_active_owner)
        for entry in self._ability_layout_cache:
            x = entry['x']; y = entry['y']; w = entry['width']; h = entry['height']
            affordable = entry['affordable']
            base_color = (40, 100, 40) if affordable else (120, 40, 40)
            if entry['is_active'] and not entry['is_targeting']:
                r,g,b = base_color
                bg_color = (min(255, r+30), min(255, g+30), min(255, b+30))
            else:
                bg_color = base_color
            border_color = (200, 200, 200)
            points = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            if headless:
                continue
            if hasattr(arcade, 'draw_polygon_filled'):
                if entry['is_targeting']:
                    arcade.draw_polygon_filled(points, (70, 130, 180))
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

    def get_regiment_at_point(self, x: float, y: float):
        """Return regiment layout entry if point falls within its circle."""
        cache = getattr(self, '_regiment_layout_cache', None)
        if not cache:
            return None
        for entry in cache:
            dx = x - entry['center_x']
            dy = y - entry['center_y']
            if dx * dx + dy * dy <= entry['radius'] * entry['radius']:
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

    # --------------------------------------------------------------
    # Regiment Visualization
    # --------------------------------------------------------------
    def _render_regiments(self, arcade, registry: TileTypes, board_left: float, board_right: float, board_top: float) -> None:
        rosters = sorted(self.world.get_component(ArmyRoster), key=lambda pair: pair[0])
        if not rosters:
            self._regiment_layout_cache = []
            return

        active_regiment_entities: set[int] = set()
        for _, roster in rosters:
            active_regiment_entities.update(roster.regiment_entities)
        self._cleanup_regiment_sprites(active_regiment_entities)

        total_width = board_right - board_left
        window_w = self.window.width
        left_space = max(0, board_left - SIDE_GAP)
        right_space = max(0, (window_w - board_right) - SIDE_GAP)
        left_col_w = max(SIDE_PANEL_MIN_WIDTH, left_space)
        right_col_w = max(SIDE_PANEL_MIN_WIDTH, right_space)
        left_panel_left = board_left - SIDE_GAP - left_col_w
        right_panel_left = board_right + SIDE_GAP
        left_panel_center = left_panel_left + left_col_w / 2
        right_panel_center = right_panel_left + right_col_w / 2

        circle_spacing = 110
        base_radius = 36
        active_radius = 52
        outline_color = (245, 245, 245)
        active_y = board_top + 110
        inactive_y = board_top + 70
        bank_offsets = [-0.6, 0.6, -1.2, 1.2]
        text_commands: list[tuple[str, float, float, tuple[int, int, int], int]] = []
        layout_cache = []

        for index, (owner_entity, roster) in enumerate(rosters):
            if not roster.regiment_entities:
                continue
            is_first_player = index == 0
            panel_center = left_panel_center if is_first_player else right_panel_center
            active_x = board_left + total_width * 0.25 if is_first_player else board_right - total_width * 0.25

            non_active_slots = [slot for slot in range(len(roster.regiment_entities)) if slot != roster.active_index]
            position_by_slot: dict[int, tuple[float, float, float]] = {}
            position_by_slot[roster.active_index] = (active_x, active_y, active_radius)

            for pos_idx, slot in enumerate(non_active_slots):
                offset = bank_offsets[pos_idx] if pos_idx < len(bank_offsets) else bank_offsets[-1]
                center_x = panel_center + offset * circle_spacing
                position_by_slot[slot] = (center_x, inactive_y, base_radius)

            for slot, regiment_entity in enumerate(roster.regiment_entities):
                coords = position_by_slot.get(slot)
                if coords is None:
                    continue
                center_x, center_y, radius = coords
                try:
                    regiment: Regiment = self.world.component_for_entity(regiment_entity, Regiment)
                except KeyError:
                    continue

                try:
                    fill_color = registry.background_for(regiment.unit_type)
                except KeyError:
                    fill_color = (180, 180, 180)

                can_attack = (
                    self._current_active_owner is not None and
                    owner_entity == self._current_active_owner and
                    slot == roster.active_index and
                    regiment.battle_readiness >= self._attack_threshold
                )
                if can_attack:
                    pulse = (math.sin(self._time * 3.0) + 1.0) * 0.5
                    glow_radius = radius + 10 + pulse * 6
                    glow_alpha = int(80 + pulse * 100)
                    glow_color = (90, 255, 150, glow_alpha)
                    arcade.draw_circle_filled(center_x, center_y, glow_radius, glow_color)
                arcade.draw_circle_filled(center_x, center_y, radius, fill_color)
                outline_thickness = 4 if slot == roster.active_index else 2
                arcade.draw_circle_outline(center_x, center_y, radius + outline_thickness, outline_color, outline_thickness)

                sprite = self._ensure_regiment_sprite(arcade, regiment_entity, regiment.unit_type)
                if sprite is not None:
                    icon_size = radius * 1.6
                    self._update_sprite_visuals(sprite, center_x, center_y, icon_size, 255)
                layout_cache.append({
                    'owner_entity': owner_entity,
                    'regiment_entity': regiment_entity,
                    'center_x': center_x,
                    'center_y': center_y,
                    'radius': radius,
                    'is_active': slot == roster.active_index,
                })

                morale_text = f"Morale {regiment.morale:.0f}"
                text_commands.append((morale_text, center_x, center_y + radius + 30, (240, 240, 240), 12))
                text_commands.append((regiment.unit_type.title(), center_x, center_y + radius + 12, (220, 220, 220), 12))
                readiness_text = str(regiment.battle_readiness)
                text_commands.append((readiness_text, center_x, center_y - radius - 24, (230, 230, 230), 12))

        self._regiment_layout_cache = layout_cache

        if self._regiment_sprites is not None:
            self._regiment_sprites.draw()

        for text, x, y, color_val, font_size in text_commands:
            arcade.draw_text(
                text,
                x,
                y,
                color_val,
                font_size,
                anchor_x="center",
            )

    # --------------------------------------------------------------
    # Side Panels (Bank bar + Ability panel)
    # --------------------------------------------------------------
    def _render_side_panels(self, arcade, registry: TileTypes, board_start_y: float, tile_size: int):
        """Draw horizontal bank bars above ability panels on both sides.

        Sketch target:
          [ BANK BAR ]   BOARD   [ BANK BAR ]
          [ ABILITIES ]          [ ABILITIES ]

        Bank bar bottom aligns with board top (board_start_y + GRID_ROWS*tile_size).
        """
        total_width = GRID_COLS * tile_size
        board_left = (self.window.width - total_width) / 2
        board_right = board_left + total_width
        board_top = board_start_y + GRID_ROWS * tile_size
        banks = list(self.world.get_component(TileBank))
        if not banks:
            return
        banks_sorted = sorted(banks, key=lambda pair: pair[1].owner_entity)
        visible_types = {"tactics", "subterfuge", "logistics"}
        # Panel rectangles (dynamic widths consume remaining horizontal space)
        window_w = self.window.width
        left_space = max(0, board_left - SIDE_GAP)
        right_space = max(0, (window_w - board_right) - SIDE_GAP)
        left_col_w = max(SIDE_PANEL_MIN_WIDTH, left_space)
        right_col_w = max(SIDE_PANEL_MIN_WIDTH, right_space)
        left_panel_left = board_left - SIDE_GAP - left_col_w
        right_panel_left = board_right + SIDE_GAP
        panel_bottom = board_start_y  # ability panel spans full column
        panel_top = board_top
        panel_color = (20, 20, 20)
        border_color = (180,180,180)
        # Draw ability panel backgrounds
        for side, col_w in (('left', left_col_w), ('right', right_col_w)):
            x = left_panel_left if side == 'left' else right_panel_left
            # Ability panel rectangle (exclude bank bar height from background so bar can have distinct style)
            ability_bottom = panel_bottom
            # Ability panel excludes bank bar height at top.
            ability_top = panel_top - BANK_BAR_HEIGHT
            points = [
                (x, ability_bottom), (x + col_w, ability_bottom),
                (x + col_w, ability_top), (x, ability_top)
            ]
            arcade.draw_polygon_filled(points, panel_color)
            arcade.draw_polygon_outline(points, border_color, 2)
            # Bank bar rectangle directly above
            bar_bottom = panel_top - BANK_BAR_HEIGHT
            bar_top = panel_top
            bar_points = [
                (x, bar_bottom), (x + col_w, bar_bottom),
                (x + col_w, bar_top), (x, bar_top)
            ]
            arcade.draw_polygon_filled(bar_points, (35,35,35))
            arcade.draw_polygon_outline(bar_points, border_color, 2)
        # Render bank contents inside each bank bar
        circle_radius = 32
        ordered_types = ["tactics", "logistics", "subterfuge"]
        for idx, (bank_ent, bank) in enumerate(banks_sorted):
            bar_left = left_panel_left if idx == 0 else right_panel_left
            bar_bottom = panel_top - BANK_BAR_HEIGHT
            center_y = bar_bottom + BANK_BAR_HEIGHT/2
            col_w = left_col_w if idx == 0 else right_col_w
            pad_left = bar_left + 32
            pad_right = bar_left + col_w - 32
            full_span = max(0, pad_right - pad_left)
            # Use a centered reduced span (e.g., 60% of full) to cluster circles toward middle.
            cluster_ratio = 0.6
            cluster_width = full_span * cluster_ratio
            cluster_left = pad_left + (full_span - cluster_width) / 2
            cluster_right = cluster_left + cluster_width
            span_width = cluster_width
            # Fixed positions: equally spaced across span for the three resource types.
            positions = []
            slots = len(ordered_types)
            if slots == 1:
                positions = [cluster_left + span_width/2]
            else:
                step = span_width / (slots - 1) if slots > 1 else 0
                positions = [cluster_left + i * step for i in range(slots)]
            for type_name, cx in zip(ordered_types, positions):
                count = bank.counts.get(type_name, 0)
                try:
                    color_tuple = registry.background_for(type_name)
                except Exception:
                    color_tuple = (80,80,80)
                arcade.draw_circle_filled(cx, center_y, circle_radius, color_tuple)
                arcade.draw_circle_outline(cx, center_y, circle_radius, (255,255,255), 2)
                icon_sprite = self._ensure_bank_row_sprite(arcade, bank_ent, type_name)
                if icon_sprite is not None:
                    self._update_sprite_visuals(icon_sprite, cx, center_y, icon_size=circle_radius*1.2, alpha=255, tint_color=None)
                count_y = center_y - circle_radius - 6
                arcade.draw_text(str(count), cx - 12, count_y, arcade.color.WHITE, 16)
        if self._bank_icon_sprites is not None:
            self._bank_icon_sprites.draw()

