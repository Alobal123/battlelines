"""Rendering helper for the generic choice window overlay."""
from __future__ import annotations

from typing import Dict, Tuple, TYPE_CHECKING

from ecs.components.choice_window import ChoiceWindow, ChoiceOption

if TYPE_CHECKING:
    from ecs.systems.render import RenderSystem


class ChoiceWindowRenderer:
    """Draws choice panels when a ChoiceWindow exists."""

    def __init__(self, render_system: "RenderSystem") -> None:
        self._rs = render_system
        self._option_layout: Dict[int, Tuple[float, float, float, float]] = {}
        self._skip_bounds: Tuple[float, float, float, float] | None = None
        self._active_choice_icon_keys: set[tuple[int, int]] = set()

    def render(self, arcade, ctx, *, headless: bool) -> None:
        world = self._rs.world
        sprite_cache = getattr(self._rs, "sprite_cache", None)
        self._active_choice_icon_keys = set()
        windows = list(world.get_component(ChoiceWindow))
        if not windows:
            self._option_layout.clear()
            self._skip_bounds = None
            if sprite_cache is not None:
                sprite_cache.cleanup_choice_cost_sprites(set())
            return

        # At the moment support a single active window; use first entry.
        window_entity, window = windows[0]
        options = [
            (ent, comp) for ent, comp in world.get_component(ChoiceOption)
            if comp.window_entity == window_entity
        ]
        options.sort(key=lambda pair: pair[1].order)

        if not options:
            window.option_entities = []
            window.skip_button_bounds = None
            self._option_layout.clear()
            self._skip_bounds = None
            if sprite_cache is not None:
                sprite_cache.cleanup_choice_cost_sprites(set())
            return

        window.option_entities = [ent for ent, _ in options]

        total_width = 0.0
        gap = window.panel_gap
        widest_height = 0.0
        for _, opt in options:
            total_width += opt.width
            widest_height = max(widest_height, opt.height)
        if options:
            total_width += gap * (len(options) - 1)

        margin = 80.0
        start_x = max(margin, (ctx.window_width - total_width) / 2.0)
        panel_bottom = ctx.window_height * 0.5 - widest_height / 2.0

        overlay_color = window.overlay_color
        # Update layout cache even in headless mode.
        layout = {}
        current_left = start_x
        for ent, opt in options:
            bounds = (current_left, panel_bottom, opt.width, opt.height)
            opt.bounds = bounds
            layout[ent] = bounds
            current_left += opt.width + gap
        self._option_layout = layout

        # Skip button layout if enabled
        skip_bounds = None
        if window.skippable:
            skip_width = 180.0
            skip_height = 48.0
            skip_left = (ctx.window_width - skip_width) / 2.0
            skip_bottom = panel_bottom - skip_height - 32.0
            skip_bounds = (skip_left, skip_bottom, skip_width, skip_height)
            window.skip_button_bounds = skip_bounds
        else:
            window.skip_button_bounds = None
        self._skip_bounds = skip_bounds

        if headless:
            if sprite_cache is not None:
                sprite_cache.cleanup_choice_cost_sprites(set())
            return

        # Dim the background with translucent overlay.
        arcade.draw_lrbt_rectangle_filled(
            0.0,
            ctx.window_width,
            0.0,
            ctx.window_height,
            overlay_color,
        )

        panel_color = (40, 46, 70)
        border_color = (200, 200, 220)
        text_color = (240, 240, 255)

        if window.title:
            arcade.draw_text(
                window.title,
                ctx.window_width / 2.0,
                panel_bottom + widest_height + 56.0,
                text_color,
                28,
                anchor_x="center",
                anchor_y="center",
                bold=True,
            )

        try:
            tile_types = self._rs._registry()
        except Exception:
            tile_types = None

        for ent, opt in options:
            left, bottom, width, height = layout[ent]
            arcade.draw_lbwh_rectangle_filled(left, bottom, width, height, panel_color)
            arcade.draw_lbwh_rectangle_outline(left, bottom, width, height, border_color, border_width=2)

            inner_pad = 16.0
            content_width = max(0.0, width - inner_pad * 2.0)
            label_font_size = 22
            label_center_y = min(bottom + height - inner_pad - label_font_size / 2.0, bottom + height - 28.0)
            label_center_y = max(label_center_y, bottom + inner_pad + label_font_size / 2.0)
            arcade.draw_text(
                opt.label,
                left + width / 2,
                label_center_y,
                text_color,
                label_font_size,
                anchor_x="center",
                anchor_y="center",
                bold=True,
            )

            try:
                ability_cost = opt.metadata.get("ability_cost") if opt.metadata else None
            except AttributeError:
                ability_cost = None

            description_top = label_center_y - label_font_size / 2 - 18.0
            cost_entries: list[tuple[str, int]] = []
            cost_dict: dict[str, int] = {}
            if ability_cost:
                try:
                    cost_dict = {name: int(amt) for name, amt in ability_cost.items() if int(amt) > 0}
                    cost_entries = list(cost_dict.items())
                except AttributeError:
                    cost_dict = {}
                    cost_entries = []
            if cost_entries:
                available_width = content_width
                icon_size, spacing, offset = self._cost_icon_layout(
                    [amt for _, amt in cost_entries],
                    available_width,
                )
                if icon_size > 0.0:
                    cost_bottom = max(bottom + inner_pad, description_top - 12.0 - icon_size)
                    self._draw_cost_icons(
                        arcade,
                        tile_types,
                        cost_dict,
                        option_entity=ent,
                        start_x=left + inner_pad + offset,
                        panel_right=left + inner_pad + content_width,
                        start_y=cost_bottom,
                        icon_size=icon_size,
                        spacing=spacing,
                        overlay_amount=False,
                    )
                    description_top = cost_bottom - 18.0

            if opt.description:
                description_top = min(description_top, bottom + height - inner_pad)
                description_top = max(description_top, bottom + inner_pad + 4.0)
                arcade.draw_text(
                    opt.description,
                    left + inner_pad,
                    description_top,
                    text_color,
                    14,
                    anchor_x="left",
                    anchor_y="top",
                    width=content_width,
                    multiline=True,
                )

        if sprite_cache is not None:
            sprite_cache.draw_choice_cost_sprites()
            sprite_cache.cleanup_choice_cost_sprites(self._active_choice_icon_keys)

        if skip_bounds is not None:
            left, bottom, width, height = skip_bounds
            arcade.draw_lbwh_rectangle_filled(left, bottom, width, height, (60, 60, 60))
            arcade.draw_lbwh_rectangle_outline(left, bottom, width, height, border_color, border_width=2)
            arcade.draw_text(
                "Skip",
                left + width / 2,
                bottom + height / 2,
                text_color,
                18,
                anchor_x="center",
                anchor_y="center",
                bold=True,
            )

    def option_layout(self) -> Dict[int, Tuple[float, float, float, float]]:
        return self._option_layout

    def skip_bounds(self) -> Tuple[float, float, float, float] | None:
        return self._skip_bounds

    def _cost_icon_layout(
        self,
        amounts: list[int],
        available_width: float,
    ) -> tuple[float, float, float]:
        count = len(amounts)
        if count <= 0 or available_width <= 0:
            return 0.0, 0.0, 0.0
        min_size = 14.0
        max_size = min(56.0, available_width / count)
        if max_size < min_size:
            max_size = min_size

        def _row_metrics(size: float) -> tuple[float, float]:
            spacing = size * 0.35 if count > 1 else 0.0
            font_px = max(12.0, size * 0.5)
            total = 0.0
            for amt in amounts:
                text_width = max(len(str(int(amt))) * font_px * 0.6, size * 0.35)
                total += size + 6.0 + text_width
            if count > 1:
                total += spacing * (count - 1)
            return total, spacing

        best_size = min_size
        best_spacing = 0.0
        left = min_size
        right = max_size
        for _ in range(24):
            mid = (left + right) / 2.0
            total, spacing = _row_metrics(mid)
            if total <= available_width or mid <= min_size + 0.25:
                best_size = mid
                best_spacing = spacing
                left = mid
            else:
                right = mid
        total_width, _ = _row_metrics(best_size)
        offset = max(0.0, (available_width - total_width) / 2.0)
        return best_size, best_spacing, offset

    def _draw_cost_icons(
        self,
        arcade,
        tile_types,
        cost_mapping,
        *,
        option_entity: int,
        start_x: float,
        panel_right: float,
        start_y: float,
        icon_size: float | None = None,
        spacing: float | None = None,
        overlay_amount: bool = False,
    ) -> float:
        if not cost_mapping:
            return 0.0
        try:
            items = list(cost_mapping.items())
        except AttributeError:
            return 0.0
        if not items:
            return 0.0
        if icon_size is None:
            icon_size = 22.0
        if spacing is None:
            spacing = icon_size * 0.45
        x = start_x
        y = start_y
        max_drawn_size = 0.0
        sprite_cache = getattr(self._rs, "sprite_cache", None)
        for slot_index, (type_name, amount) in enumerate(sorted(items)):
            if amount <= 0:
                continue
            try:
                base_color = tile_types.background_for(type_name) if tile_types is not None else None
            except Exception:
                base_color = None
            if base_color is None:
                base_color = (120, 120, 130)
            center_x = x + icon_size / 2.0
            center_y = y + icon_size / 2.0
            radius = icon_size / 2.0
            arcade.draw_circle_filled(center_x, center_y, radius, base_color)
            arcade.draw_circle_outline(center_x, center_y, radius, (255, 255, 255), 1)
            sprite = None
            if (
                sprite_cache is not None
                and hasattr(sprite_cache, "ensure_choice_cost_sprite")
            ):
                sprite = sprite_cache.ensure_choice_cost_sprite(arcade, option_entity, slot_index, type_name)
                if sprite is not None and hasattr(sprite_cache, "update_sprite_visuals"):
                    sprite_cache.update_sprite_visuals(sprite, center_x, center_y, radius * 1.2, 255)
            if sprite is not None and hasattr(self, "_active_choice_icon_keys"):
                self._active_choice_icon_keys.add((option_entity, slot_index))
            amount_str = str(int(amount))
            if overlay_amount:
                arcade.draw_text(
                    amount_str,
                    center_x,
                    center_y,
                    (255, 255, 255),
                    max(12, int(icon_size * 0.55)),
                    anchor_x="center",
                    anchor_y="center",
                    bold=True,
                )
                x += icon_size + spacing
            else:
                right = center_x + radius
                text_y = center_y - icon_size * 0.3
                text_color = (255, 255, 255)
                font_size = max(12, int(round(icon_size * 0.5)))
                font_width = max(len(amount_str) * max(font_size, 12) * 0.6, icon_size * 0.35)
                desired_x = right + 6.0
                max_allowed = panel_right - font_width
                text_x = min(desired_x, max_allowed)
                text_x = max(text_x, start_x)
                arcade.draw_text(amount_str, text_x, text_y, text_color, font_size)
                x = text_x + font_width + spacing
            max_drawn_size = max(max_drawn_size, icon_size)
        return max_drawn_size
