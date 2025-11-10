from pathlib import Path
from typing import Any

from ecs.events.bus import (EVENT_TICK, EventBus, EVENT_TILE_SELECTED, EVENT_TILE_DESELECTED,
                            EVENT_MATCH_FOUND, EVENT_MATCH_CLEARED,
                            EVENT_TILE_SWAP_REQUEST, EVENT_TILE_SWAP_FINALIZE)
from ecs.components.tile_type_registry import TileTypeRegistry
from ecs.components.tile_types import TileTypes
from ecs.components.active_turn import ActiveTurn
from ecs.systems.battle import BattleConfig
from ecs.rendering.context import RenderContext, build_render_context, collect_animation_maps
from ecs.rendering.board_renderer import BoardRenderer
from ecs.rendering.ability_panel_renderer import AbilityPanelRenderer
from ecs.rendering.bank_panel_renderer import BankPanelRenderer
from ecs.rendering.regiment_renderer import RegimentRenderer
from ecs.rendering.sprite_cache import SpriteCache
from ecs.constants import (
    GRID_ROWS, GRID_COLS, TILE_SIZE, BOTTOM_MARGIN,
    BOARD_MAX_WIDTH_PCT, BOARD_MAX_HEIGHT_PCT,
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
        self.sprite_cache = SpriteCache(self._texture_dir)
        self._regiment_layout_cache = []
        self._ability_layout_cache = []
        self._time = 0.0
        self._attack_threshold = BattleConfig().minimum_readiness_to_attack
        self._current_active_owner: int | None = None
        self._render_ctx: RenderContext | None = None
        self._last_draw_coords: dict[tuple[int, int], tuple[float, float]] = {}
        self._board_renderer = BoardRenderer(self, self.sprite_cache, padding=PADDING)
        self._ability_panel_renderer = AbilityPanelRenderer(self)
        self._bank_panel_renderer = BankPanelRenderer(self, self.sprite_cache)
        self._regiment_renderer = RegimentRenderer(self, self.sprite_cache)

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
        board_width = tile_size * GRID_COLS
        board_left = (self.window.width - board_width) / 2
        board_bottom = BOTTOM_MARGIN
        swap_by_pos, fall_by_dst, refill_by_pos, fade_by_pos = collect_animation_maps(self.world)

        ctx = build_render_context(
            world=self.world,
            window_width=self.window.width,
            window_height=self.window.height,
            rows=GRID_ROWS,
            cols=GRID_COLS,
            tile_size=tile_size,
            board_left=board_left,
            board_bottom=board_bottom,
            swap_by_pos=swap_by_pos,
            fall_by_dst=fall_by_dst,
            refill_by_pos=refill_by_pos,
            fade_by_pos=fade_by_pos,
        )
        self._render_ctx = ctx

        registry = self._registry()
        try:
            active_turn_entries = list(self.world.get_component(ActiveTurn))
            if active_turn_entries:
                self._current_active_owner = active_turn_entries[0][1].owner_entity
            else:
                self._current_active_owner = None
        except Exception:
            self._current_active_owner = None
        self._board_renderer.render(arcade, ctx, registry, headless=headless)

        if not headless:
            # Draw panel bases before ability rectangles so overlays remain visible.
            self._bank_panel_renderer.render(arcade, ctx, registry)

        self._ability_panel_renderer.render(arcade, ctx, headless=headless)

        if not headless:
            self._regiment_renderer.render(arcade, ctx, registry)

    def get_ability_at_point(self, x: float, y: float):
        """Return ability layout entry if point inside its rectangle."""
        hit = self._ability_panel_renderer.hit_test(x, y)
        if hit is not None:
            return hit
        return None

    def get_regiment_at_point(self, x: float, y: float):
        """Return regiment layout entry if point falls within its circle."""
        hit = self._regiment_renderer.hit_test(x, y)
        if hit is not None:
            return hit
        return None

    def on_match_found(self, sender, **kwargs):
        # Notification only; no immediate action required.
        return

    def on_match_cleared(self, sender, **kwargs):
        return

    def on_swap_request(self, sender, **kwargs):
        # Clear selection immediately when a swap begins
        self.selected = None

    def on_swap_finalize(self, sender, **kwargs):
        # Ensure selection cleared after swap completes
        self.selected = None

    def _registry(self) -> TileTypes:
        for ent, _ in self.world.get_component(TileTypeRegistry):
            return self.world.component_for_entity(ent, TileTypes)
        raise RuntimeError('TileTypes definitions not found')

