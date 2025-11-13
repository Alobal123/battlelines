from typing import Dict, Tuple

from esper import World

from ecs.components.health import Health
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.rendering.context import RenderContext


class LifebarRenderer:
    """Draw simple lifebars for each player entity."""

    def __init__(self, world: World):
        self.world = world
        self.layout_cache: Dict[int, Tuple[float, float, float, float]] = {}

    def render(self, arcade, ctx: RenderContext) -> None:
        bar_width = 220
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

        columns = [
            {
                "left": margin_x,
                "top": ctx.window_height - margin_y,
                "anchor": "left",
                "text_offset": 12,
                "text_anchor": "left",
            },
            {
                "left": ctx.window_width - margin_x - bar_width,
                "top": ctx.window_height - margin_y,
                "anchor": "right",
                "text_offset": -12,
                "text_anchor": "right",
            },
        ]

        for idx, (ent, health) in enumerate(ordered_players):
            column_idx = idx % len(columns) if columns else 0
            column = columns[column_idx]
            left = column["left"]
            top = column["top"]
            pct = max(0.0, min(1.0, health.current / health.max_hp)) if health.max_hp > 0 else 0.0
            right = left + bar_width
            bottom = top - bar_height
            arcade.draw_lrbt_rectangle_outline(left, right, bottom, top, (255, 255, 255), border_width=2)
            fill_width = max(0, int(bar_width * pct))
            if fill_width > 0:
                arcade.draw_lrbt_rectangle_filled(left + 1, left + 1 + fill_width, bottom + 1, top - 1, (int(255 * (1 - pct)), int(210 * pct), 70))
            text = f"HP {health.current}/{health.max_hp}"
            text_x = right + column["text_offset"] if column_idx == 0 else left + column["text_offset"]
            arcade.draw_text(text, text_x, bottom + 2, (235, 235, 235), 12, anchor_x=column["text_anchor"])
            self.layout_cache[ent] = (left, bottom, bar_width, bar_height)
            column["top"] -= (bar_height + spacing)
