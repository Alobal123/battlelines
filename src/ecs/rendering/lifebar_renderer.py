from typing import Any, Dict, Tuple

from esper import World

from ecs.components.health import Health
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.rendering.context import RenderContext


class LifebarRenderer:
    """Draw simple lifebars for each player entity."""

    def __init__(self, world: World):
        self.world = world
        self.layout_cache: Dict[int, Tuple[float, float, float, float]] = {}

    def render(self, arcade, ctx: RenderContext, panel_layout: list[Dict[str, Any]] | None = None) -> None:
        default_bar_width = 220
        bar_height = 18
        margin_x = 24
        margin_y = 24
        spacing = 10

        ordered_players: list[tuple[int, Health]] = []
        for player_ent, _ in sorted(self.world.get_component(AbilityListOwner), key=lambda pair: pair[0]):
            try:
                health = self.world.component_for_entity(player_ent, Health)
            except KeyError:
                continue
            ordered_players.append((player_ent, health))
        if not ordered_players:
            # Fallback to any health component (e.g., headless tests without AbilityListOwner wiring).
            ordered_players = list(self.world.get_component(Health))

        panel_lookup: Dict[int, Dict[str, Any]] = {}
        if panel_layout:
            for entry in panel_layout:
                owner = entry.get("owner_entity")
                if owner is not None:
                    panel_lookup[int(owner)] = entry

        columns = [
            {
                "left": margin_x,
                "top": ctx.window_height - margin_y,
            },
            {
                "left": ctx.window_width - margin_x - default_bar_width,
                "top": ctx.window_height - margin_y,
            },
        ]

        for idx, (ent, health) in enumerate(ordered_players):
            panel_entry = panel_lookup.get(ent)
            pct = max(0.0, min(1.0, health.current / health.max_hp)) if health.max_hp > 0 else 0.0

            if panel_entry:
                portrait_left = float(panel_entry.get("portrait_left", panel_entry.get("x", 0.0)))
                portrait_bottom = float(panel_entry.get("portrait_bottom", panel_entry.get("y", 0.0)))
                portrait_size = float(panel_entry.get("portrait_size", default_bar_width))
                portrait_top = float(panel_entry.get("portrait_top", portrait_bottom + portrait_size))
                left = portrait_left + 8.0
                bar_width = max(60.0, portrait_size - 16.0)
                right = left + bar_width
                top = portrait_top - 6.0
                bottom = top - bar_height
                text_x = left + bar_width / 2
                anchor_x = "center"
            else:
                column_idx = idx % len(columns) if columns else 0
                column = columns[column_idx]
                left = column["left"]
                bar_width = default_bar_width
                top = column["top"]
                right = left + bar_width
                bottom = top - bar_height
                text_x = right - 8 if column_idx else left + bar_width + 12
                anchor_x = "right" if column_idx else "left"
                column["top"] -= (bar_height + spacing)

            arcade.draw_lrbt_rectangle_outline(left, right, bottom, top, (255, 255, 255), border_width=2)
            fill_width = max(0, int(bar_width * pct))
            if fill_width > 0:
                arcade.draw_lrbt_rectangle_filled(left + 1, left + 1 + fill_width, bottom + 1, top - 1, (int(255 * (1 - pct)), int(210 * pct), 70))
            text = f"HP {health.current}/{health.max_hp}"
            arcade.draw_text(text, text_x, bottom + 2, (235, 235, 235), 12, anchor_x=anchor_x)
            self.layout_cache[ent] = (left, bottom, bar_width, bar_height)
