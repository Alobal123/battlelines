"""Rendering helper for the generic choice window overlay."""
from __future__ import annotations

from typing import Dict, Tuple

from ecs.components.choice_window import ChoiceWindow, ChoiceOption


class ChoiceWindowRenderer:
    """Draws choice panels when a ChoiceWindow exists."""

    def __init__(self, render_system: "RenderSystem") -> None:
        self._rs = render_system
        self._option_layout: Dict[int, Tuple[float, float, float, float]] = {}
        self._skip_bounds: Tuple[float, float, float, float] | None = None

    def render(self, arcade, ctx, *, headless: bool) -> None:
        world = self._rs.world
        windows = list(world.get_component(ChoiceWindow))
        if not windows:
            self._option_layout.clear()
            self._skip_bounds = None
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

        for ent, opt in options:
            left, bottom, width, height = layout[ent]
            arcade.draw_lbwh_rectangle_filled(left, bottom, width, height, panel_color)
            arcade.draw_lbwh_rectangle_outline(left, bottom, width, height, border_color, border_width=2)
            arcade.draw_text(
                opt.label,
                left + width / 2,
                bottom + height - 32,
                text_color,
                20,
                anchor_x="center",
                anchor_y="center",
                bold=True,
            )
            if opt.description:
                arcade.draw_text(
                    opt.description,
                    left + 16,
                    bottom + height - 64,
                    text_color,
                    14,
                    anchor_x="left",
                    anchor_y="top",
                    width=width - 32,
                    multiline=True,
                )

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
