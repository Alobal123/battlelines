from esper import World

from ecs.components.forbidden_knowledge import ForbiddenKnowledge
from ecs.rendering.context import RenderContext


class ForbiddenKnowledgeRenderer:
    """Draws a centered meter showing accumulated Forbidden Knowledge."""

    def __init__(self, world: World):
        self.world = world
        self.layout_cache: dict[int, tuple[float, float, float, float]] = {}

    def render(self, arcade, ctx: RenderContext) -> None:
        entries = list(self.world.get_component(ForbiddenKnowledge))
        if not entries:
            return
        entity, meter = entries[0]
        if meter.max_value <= 0:
            return

        bar_width = 260
        bar_height = 18
        margin_top = 24
        center_x = ctx.window_width / 2
        top = ctx.window_height - margin_top
        bottom = top - bar_height
        left = center_x - bar_width / 2
        right = left + bar_width

        arcade.draw_lrbt_rectangle_outline(left, right, bottom, top, (210, 210, 230), border_width=2)
        arcade.draw_lrbt_rectangle_filled(left + 1, right - 1, bottom + 1, top - 1, (24, 24, 36))

        pct = max(0.0, min(1.0, meter.value / meter.max_value))
        fill_width = int((bar_width - 4) * pct)
        if fill_width > 0:
            arcade.draw_lrbt_rectangle_filled(
                left + 2,
                left + 2 + fill_width,
                bottom + 2,
                top - 2,
                (108, 92, 231),
            )

        label = f"Forbidden Knowledge {meter.value}/{meter.max_value}"
        arcade.draw_text(label, center_x, bottom + 2, arcade.color.WHITE, 12, anchor_x="center")
        self.layout_cache[entity] = (left, bottom, bar_width, bar_height)

    def hit_test(self, x: float, y: float) -> dict[str, int] | None:
        for entity, (left, bottom, width, height) in self.layout_cache.items():
            if left <= x <= left + width and bottom <= y <= bottom + height:
                return {"entity": entity}
        return None
