from __future__ import annotations

from typing import TYPE_CHECKING

from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.character import Character
from ecs.constants import (
    PLAYER_PANEL_HEIGHT,
    PLAYER_PORTRAIT_PADDING,
    SIDE_GAP,
    SIDE_PANEL_MIN_WIDTH,
    SIDE_PANEL_TOP_MARGIN,
)
from ecs.rendering.highlight_profiles import (
    ACTIVE_PORTRAIT_ALPHA,
    ACTIVE_PORTRAIT_TINT,
    INACTIVE_PORTRAIT_ALPHA,
    INACTIVE_PORTRAIT_TINT,
)

if TYPE_CHECKING:
    from ecs.rendering.context import RenderContext
    from ecs.systems.render import RenderSystem


class PlayerPanelRenderer:
    """Render the player label strip and portrait block for each side panel."""

    def __init__(self, render_system: RenderSystem):
        self._rs = render_system

    def render(self, arcade, ctx: RenderContext) -> None:
        board_left = ctx.board_left
        board_right = ctx.board_right
        panel_top = ctx.window_height - SIDE_PANEL_TOP_MARGIN
        window_w = ctx.window_width
        left_space = max(0, board_left - SIDE_GAP)
        right_space = max(0, (window_w - board_right) - SIDE_GAP)
        left_col_w = max(SIDE_PANEL_MIN_WIDTH, left_space)
        right_col_w = max(SIDE_PANEL_MIN_WIDTH, right_space)
        left_panel_left = board_left - SIDE_GAP - left_col_w
        right_panel_left = board_right + SIDE_GAP

        rs = self._rs
        rs._player_panel_cache = []
        owners = list(rs.world.get_component(AbilityListOwner))
        owners.sort(key=lambda item: item[0])
        owner_by_side: dict[str, int] = {}
        character_by_side: dict[str, Character | None] = {}
        for idx, (entity, _owner) in enumerate(owners):
            side = "left" if idx == 0 else "right" if idx == 1 else None
            if side:
                owner_by_side[side] = entity
                # Try to get Character component
                try:
                    character = rs.world.component_for_entity(entity, Character)
                    character_by_side[side] = character
                except KeyError:
                    character_by_side[side] = None
            if idx >= 1:
                break

        active_portrait_keys = {
            character.portrait_path
            for character in character_by_side.values()
            if character and character.portrait_path
        }
        rs.sprite_cache.cleanup_portrait_sprites(active_portrait_keys)

        active_owner = getattr(rs, "_current_active_owner", None)

        def _colors_for(highlight: bool):
            if highlight:
                return {
                    "panel": (70, 70, 100),
                    "border": (230, 230, 230),
                    "portrait_bg": (45, 45, 70),
                    "label": arcade.color.ANTIQUE_WHITE,
                    "alpha": ACTIVE_PORTRAIT_ALPHA,
                    "tint": ACTIVE_PORTRAIT_TINT,
                }
            return {
                "panel": (40, 40, 40),
                "border": (130, 130, 130),
                "portrait_bg": (25, 25, 25),
                "label": (170, 170, 170),
                "alpha": INACTIVE_PORTRAIT_ALPHA,
                "tint": INACTIVE_PORTRAIT_TINT,
            }

        for side, col_w in (("left", left_col_w), ("right", right_col_w)):
            x = left_panel_left if side == "left" else right_panel_left
            owner_entity = owner_by_side.get(side)
            character = character_by_side.get(side)
            highlight = owner_entity is not None and owner_entity == active_owner
            colors = _colors_for(highlight)
            
            player_bottom = panel_top - PLAYER_PANEL_HEIGHT
            player_points = [
                (x, player_bottom),
                (x + col_w, player_bottom),
                (x + col_w, panel_top),
                (x, panel_top),
            ]
            arcade.draw_polygon_filled(player_points, colors["panel"])
            arcade.draw_polygon_outline(player_points, colors["border"], 2)
            
            # Use character name if available, otherwise default label
            if character:
                label = character.name
            else:
                label = "Player 1" if side == "left" else "Player 2"
            arcade.draw_text(
                label,
                x + col_w / 2,
                player_bottom + PLAYER_PANEL_HEIGHT / 2 - 8,
                colors["label"],
                16,
                anchor_x="center",
            )

            portrait_size = col_w
            portrait_top = player_bottom
            portrait_bottom = portrait_top - portrait_size
            portrait_left = x
            portrait_right = portrait_left + portrait_size
            portrait_points = [
                (portrait_left, portrait_bottom),
                (portrait_right, portrait_bottom),
                (portrait_right, portrait_top),
                (portrait_left, portrait_top),
            ]
            arcade.draw_polygon_filled(portrait_points, colors["portrait_bg"])
            arcade.draw_polygon_outline(portrait_points, colors["border"], 2)

            # Load portrait from character component
            if character and character.portrait_path:
                portrait_path = rs._portrait_dir / character.portrait_path
                sprite = rs.sprite_cache.ensure_portrait_sprite(arcade, character.portrait_path, portrait_path)
                if sprite is not None:
                    center_x = portrait_left + portrait_size / 2
                    center_y = portrait_bottom + portrait_size / 2
                    icon_size = max(0.0, portrait_size - PLAYER_PORTRAIT_PADDING * 2)
                    rs.sprite_cache.update_sprite_visuals(
                        sprite,
                        center_x,
                        center_y,
                        icon_size,
                        colors["alpha"],
                        colors["tint"],
                    )

            if owner_entity is not None:
                rs._player_panel_cache.append(
                    {
                        "side": side,
                        "owner_entity": owner_entity,
                        "x": x,
                        "y": player_bottom,
                        "width": col_w,
                        "height": PLAYER_PANEL_HEIGHT,
                        "label": label,
                        "portrait_bottom": portrait_bottom,
                        "portrait_size": portrait_size,
                        "active": highlight,
                    }
                )

        rs.sprite_cache.draw_portrait_sprites()
