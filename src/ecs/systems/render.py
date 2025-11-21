from pathlib import Path
from typing import Any

from ecs.events.bus import (EVENT_TICK, EventBus, EVENT_TILE_SELECTED, EVENT_TILE_DESELECTED,
                            EVENT_MATCH_FOUND, EVENT_MATCH_CLEARED,
                            EVENT_TILE_SWAP_REQUEST, EVENT_TILE_SWAP_FINALIZE)
from ecs.components.tile_type_registry import TileTypeRegistry
from ecs.components.tile_types import TileTypes
from ecs.components.active_turn import ActiveTurn
from ecs.rendering.context import RenderContext, build_render_context, collect_animation_maps
from ecs.rendering.board_renderer import BoardRenderer
from ecs.rendering.ability_panel_renderer import AbilityPanelRenderer
from ecs.rendering.bank_panel_renderer import BankPanelRenderer
from ecs.rendering.player_panel_renderer import PlayerPanelRenderer
from ecs.rendering.lifebar_renderer import LifebarRenderer
from ecs.rendering.forbidden_knowledge_renderer import ForbiddenKnowledgeRenderer
from ecs.components.tooltip_state import TooltipState
from ecs.rendering.sprite_cache import SpriteCache
from ecs.rendering.choice_window_renderer import ChoiceWindowRenderer
from ecs.components.game_state import GameMode, GameState
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
        base_graphics_dir = Path(__file__).resolve().parents[3] / "graphics"
        self._texture_dir = base_graphics_dir / "icons"
        self._portrait_dir = base_graphics_dir / "characters"
        self.sprite_cache = SpriteCache(self._texture_dir)
        self._ability_layout_cache = []
        self._player_panel_cache: list[dict[str, Any]] = []
        self._time = 0.0
        # BattleConfig removed with combat system; attack threshold concept deprecated.
        self._attack_threshold = 0
        self._current_active_owner: int | None = None
        self._render_ctx: RenderContext | None = None
        self._last_draw_coords: dict[tuple[int, int], tuple[float, float]] = {}
        self._board_renderer = BoardRenderer(self, self.sprite_cache, padding=PADDING)
        self._ability_panel_renderer = AbilityPanelRenderer(self)
        self._bank_panel_renderer = BankPanelRenderer(self, self.sprite_cache)
        self._player_panel_renderer = PlayerPanelRenderer(self)
        self._lifebar_renderer = LifebarRenderer(self.world)
        self._forbidden_knowledge_renderer = ForbiddenKnowledgeRenderer(self.world)
        self._choice_window_renderer = ChoiceWindowRenderer(self)
        self._bank_icon_cache: list[dict[str, Any]] = []

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

        mode = self._current_mode()
        combat_active = mode == GameMode.COMBAT

        if combat_active:
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
                # Draw panel bases; then lifebars; then ability rectangles.
                self._player_panel_renderer.render(arcade, ctx)
                self._lifebar_renderer.render(arcade, ctx, getattr(self, "_player_panel_cache", None))
                self._forbidden_knowledge_renderer.render(arcade, ctx)
                self._bank_panel_renderer.render(arcade, ctx, registry)

            self._ability_panel_renderer.render(arcade, ctx, headless=headless)
        else:
            self._current_active_owner = None
            self._ability_layout_cache = []
            self._bank_icon_cache = []

        self._choice_window_renderer.render(arcade, ctx, headless=headless)

        if combat_active and not headless:
            self._render_tooltip(arcade)


    def get_ability_at_point(self, x: float, y: float):
        """Return ability layout entry if point inside its rectangle."""
        hit = self._ability_panel_renderer.hit_test(x, y)
        if hit is not None:
            return hit
        return None

    def get_player_panel_at_point(self, x: float, y: float):
        for entry in getattr(self, "_player_panel_cache", []):
            ex = entry.get("x", 0.0)
            ey = entry.get("y", 0.0)
            width = entry.get("width", 0.0)
            height = entry.get("height", 0.0)
            if ex <= x <= ex + width and ey <= y <= ey + height:
                return entry
            portrait_left = entry.get("portrait_left")
            portrait_bottom = entry.get("portrait_bottom")
            portrait_size = entry.get("portrait_size")
            if (
                portrait_left is not None
                and portrait_bottom is not None
                and portrait_size is not None
            ):
                portrait_top = entry.get("portrait_top", portrait_bottom + portrait_size)
                portrait_right = portrait_left + portrait_size
                if (
                    portrait_left <= x <= portrait_right
                    and portrait_bottom <= y <= portrait_top
                ):
                    return entry
        return None

    def get_forbidden_knowledge_at_point(self, x: float, y: float):
        if not hasattr(self, "_forbidden_knowledge_renderer"):
            return None
        return self._forbidden_knowledge_renderer.hit_test(x, y)

    def get_bank_icon_at_point(self, x: float, y: float):
        for entry in self._bank_icon_cache:
            cx = float(entry.get("center_x", 0.0))
            cy = float(entry.get("center_y", 0.0))
            radius = float(entry.get("radius", 0.0))
            dx = x - cx
            dy = y - cy
            if dx * dx + dy * dy <= radius * radius:
                return entry
        return None

    # Regiment interaction removed.

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

    def _current_tooltip(self) -> TooltipState | None:
        entries = list(self.world.get_component(TooltipState))
        if not entries:
            return None
        return entries[0][1]

    def _current_mode(self) -> GameMode:
        states = list(self.world.get_component(GameState))
        if not states:
            return GameMode.COMBAT
        return states[0][1].mode

    def _render_tooltip(self, arcade) -> None:
        tooltip = self._current_tooltip()
        if not tooltip or not tooltip.visible or not tooltip.lines:
            return
        left = tooltip.x
        bottom = tooltip.y
        width = tooltip.width
        height = tooltip.height
        padding = tooltip.padding
        line_height = tooltip.line_height
        bg_color = (20, 20, 30)
        border_color = (150, 150, 180)
        top = bottom + height
        arcade.draw_lrbt_rectangle_filled(left, left + width, bottom, top, bg_color)
        arcade.draw_lrbt_rectangle_outline(left, left + width, bottom, top, border_color, 2)
        text_x = left + padding
        text_y = bottom + height - padding - line_height
        for line in tooltip.lines:
            arcade.draw_text(line, text_x, text_y, arcade.color.WHITE, 12)
            text_y -= line_height

