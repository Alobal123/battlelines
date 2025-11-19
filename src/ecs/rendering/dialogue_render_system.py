from __future__ import annotations

import arcade
from esper import World

from ecs.components.character import Character
from ecs.components.dialogue_session import DialogueSession
from ecs.components.game_state import GameMode, GameState
from ecs.systems.render import RenderSystem
from ecs.rendering.highlight_profiles import (
    ACTIVE_PORTRAIT_ALPHA,
    ACTIVE_PORTRAIT_TINT,
    INACTIVE_PORTRAIT_ALPHA,
    INACTIVE_PORTRAIT_TINT,
)


class DialogueRenderSystem:
    """Renders cinematic dialogue scenes between combats."""

    def __init__(self, world: World, window, render_system: RenderSystem) -> None:
        self.world = world
        self.window = window
        self.render_system = render_system

    def process(self) -> None:
        state = self._get_game_state()
        if not state or state.mode != GameMode.DIALOGUE:
            return
        session_entry = self._get_dialogue_session()
        if session_entry is None:
            return
        entity, session = session_entry
        line = session.current_line
        if line is None:
            return

        window_w = self.window.width
        window_h = self.window.height

        background_color = (15, 15, 24, 230)
        text_bg_color = (40, 40, 60, 230)
        text_color = arcade.color.ANTIQUE_WHITE

        arcade.draw_lrbt_rectangle_filled(0, window_w, 0, window_h, background_color)

        left_x = window_w * 0.25
        right_x = window_w * 0.75
        portrait_size = min(window_h * 0.65, window_w * 0.45)
        center_y = window_h * 0.6

        left_info = self._character_info(session.left_entity)
        right_info = self._character_info(session.right_entity)

        active_side = "left" if line.speaker_entity == session.left_entity else "right"

        portrait_keys = {
            key
            for key in (
                left_info.portrait_path if left_info else None,
                right_info.portrait_path if right_info else None,
            )
            if key
        }
        self.render_system.sprite_cache.cleanup_portrait_sprites(portrait_keys)

        self._prepare_portrait(left_info, left_x, center_y, portrait_size, active_side == "left")
        self._prepare_portrait(right_info, right_x, center_y, portrait_size, active_side == "right")

        padding = 16
        text_width = min(portrait_size * 0.9, window_w * 0.45)

        if active_side == "left":
            text_left = left_x - text_width / 2
        else:
            text_left = right_x - text_width / 2
        text_left = max(padding, min(text_left, window_w - text_width - padding))

        speaker_info = left_info if active_side == "left" else right_info
        speaker_name = speaker_info.name if speaker_info else "???"
        text_content = f"{speaker_name}: {line.text}"
        text_start_x = text_left + padding

        temp_text = arcade.Text(
            text_content,
            text_start_x,
            0,
            text_color,
            font_size=20,
            width=text_width - padding * 2,
            multiline=True,
            align="left",
            anchor_x="left",
            anchor_y="bottom",
        )
        text_height = temp_text.content_height
        box_height = text_height + padding * 2
        text_bottom = max(padding, center_y - portrait_size / 2 - box_height - padding)
        text_top = text_bottom + box_height
        temp_text.y = text_bottom + padding

        arcade.draw_lbwh_rectangle_filled(
            text_left,
            text_bottom,
            text_width,
            box_height,
            text_bg_color,
        )
        arcade.draw_lbwh_rectangle_outline(
            text_left,
            text_bottom,
            text_width,
            box_height,
            arcade.color.LIGHT_STEEL_BLUE,
            border_width=3,
        )

        temp_text.draw()

        self.render_system.sprite_cache.draw_portrait_sprites()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_dialogue_session(self):
        sessions = list(self.world.get_component(DialogueSession))
        if not sessions:
            return None
        return sessions[0]

    def _get_game_state(self) -> GameState | None:
        entries = list(self.world.get_component(GameState))
        if not entries:
            return None
        return entries[0][1]

    def _character_info(self, entity: int):
        try:
            character = self.world.component_for_entity(entity, Character)
        except KeyError:
            return _RenderCharacterInfo(entity=entity, name="???", portrait_path=None)
        return _RenderCharacterInfo(
            entity=entity,
            name=character.name or "???",
            portrait_path=character.portrait_path,
        )

    def _prepare_portrait(self, info, center_x: float, center_y: float, size: float, highlight: bool) -> None:
        if info is None:
            return
        tint = ACTIVE_PORTRAIT_TINT if highlight else INACTIVE_PORTRAIT_TINT
        alpha = ACTIVE_PORTRAIT_ALPHA if highlight else INACTIVE_PORTRAIT_ALPHA
        sprite_cache = self.render_system.sprite_cache
        if not info.portrait_path:
            return
        portrait_path = self.render_system._portrait_dir / info.portrait_path
        sprite = sprite_cache.ensure_portrait_sprite(arcade, info.portrait_path, portrait_path)
        if sprite is None:
            return
        sprite_cache.update_sprite_visuals(sprite, center_x, center_y, size, alpha, tint)


class _RenderCharacterInfo:
    __slots__ = ("entity", "name", "portrait_path")

    def __init__(self, entity: int, name: str, portrait_path: str | None) -> None:
        self.entity = entity
        self.name = name
        self.portrait_path = portrait_path
