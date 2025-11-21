from __future__ import annotations

import textwrap
from typing import Optional

from esper import World

from ecs.components.tooltip_state import TooltipState
from ecs.components.ability import Ability
from ecs.components.ability_cooldown import AbilityCooldown
from ecs.components.effect_list import EffectList
from ecs.components.effect import Effect
from ecs.components.effect_duration import EffectDuration
from ecs.effects.registry import default_effect_registry
from ecs.events.bus import (
    EventBus,
    EVENT_MOUSE_MOVE,
    EVENT_TICK,
    EVENT_ABILITY_ACTIVATE_REQUEST,
)


class TooltipSystem:
    """Tracks hover targets and exposes tooltip text/geometry for rendering."""

    def __init__(self, world: World, event_bus: EventBus, window, render_system, *, delay: float = 0.35) -> None:
        self.world = world
        self.event_bus = event_bus
        self.window = window
        self.render_system = render_system
        self.delay = delay
        self._hover_token: Optional[tuple[str, int]] = None
        self._hover_time: float = 0.0
        self._hover_text: str = ""
        self._mouse_x: float = 0.0
        self._mouse_y: float = 0.0
        self._state_entity: Optional[int] = None
        self._state = self._ensure_state()
        self.event_bus.subscribe(EVENT_MOUSE_MOVE, self.on_mouse_move)
        self.event_bus.subscribe(EVENT_TICK, self.on_tick)
        self.event_bus.subscribe(EVENT_ABILITY_ACTIVATE_REQUEST, self.on_input_action)

    def _ensure_state(self) -> TooltipState:
        entries = list(self.world.get_component(TooltipState))
        if entries:
            self._state_entity, state = entries[0]
            return state
        self._state_entity = self.world.create_entity(TooltipState())
        return self.world.component_for_entity(self._state_entity, TooltipState)

    def on_mouse_move(self, sender, **payload):
        x = payload.get("x")
        y = payload.get("y")
        if x is None or y is None:
            return
        self._mouse_x = float(x)
        self._mouse_y = float(y)
        entry = None
        if self.render_system is not None and hasattr(self.render_system, "get_ability_at_point"):
            entry = self.render_system.get_ability_at_point(self._mouse_x, self._mouse_y)
        text: str = ""
        token: Optional[tuple[str, int]] = None
        if entry is not None:
            ability_entity = entry.get("entity")
            if ability_entity is not None:
                token = ("ability", int(ability_entity))
                raw_text = entry.get("description")
                if not raw_text:
                    raw_text = self._ability_description(ability_entity)
                text = raw_text or ""
        else:
            player_entry = None
            if self.render_system is not None and hasattr(self.render_system, "get_player_panel_at_point"):
                player_entry = self.render_system.get_player_panel_at_point(self._mouse_x, self._mouse_y)
            if player_entry is not None:
                owner_entity = player_entry.get("owner_entity")
                if owner_entity is not None:
                    token = ("player", int(owner_entity))
                    text = self._player_effect_text(int(owner_entity))
        if token == self._hover_token:
            # Hover target unchanged; just update mouse position
            return
        self._hover_token = token
        self._hover_time = 0.0
        self._hover_text = text
        if not token or not text:
            self._hide_tooltip()
        else:
            # Hide until delay elapses
            self._hide_tooltip()

    def on_tick(self, sender, **payload):
        if not self._hover_token or not self._hover_text:
            return
        dt = payload.get("dt", 1 / 60)
        try:
            dt_val = float(dt)
        except Exception:
            dt_val = 1 / 60
        self._hover_time += dt_val
        if self._hover_time < self.delay:
            return
        self._show_tooltip(self._hover_text)

    def on_input_action(self, sender, **payload):
        # Clear tooltip once an ability is clicked/activated.
        self._hide_tooltip()
        self._hover_token = None
        self._hover_time = 0.0
        self._hover_text = ""

    def _show_tooltip(self, text: str) -> None:
        segments = text.split("\n") if text else [""]
        wrapped: list[str] = []
        for segment in segments:
            stripped = segment.strip()
            if not stripped:
                wrapped.append("")
                continue
            wrapped.extend(textwrap.wrap(stripped, width=42))
        lines = tuple(wrapped) if wrapped else (text,)
        padding = 8.0
        line_height = 16.0
        max_chars = max(len(line) for line in lines)
        width = padding * 2 + max_chars * 7.0
        height = padding * 2 + line_height * len(lines)
        window_w = getattr(self.window, "width", 800)
        window_h = getattr(self.window, "height", 600)
        x = self._mouse_x + 18.0
        y = self._mouse_y + 18.0
        if x + width + 4 > window_w:
            x = max(4.0, window_w - width - 4)
        if y + height + 4 > window_h:
            y = max(4.0, window_h - height - 4)
        state = self._state
        state.visible = True
        state.lines = lines
        state.x = x
        state.y = y
        state.width = width
        state.height = height
        state.padding = padding
        state.line_height = line_height
        target = self._hover_token
        if target:
            state.target = target[0]
            state.target_id = target[1]

    def _hide_tooltip(self) -> None:
        state = self._state
        state.visible = False
        state.lines = ()
        state.width = 0.0
        state.height = 0.0
        state.target = ""
        state.target_id = None

    def _ability_description(self, ability_entity: int) -> str:
        try:
            ability = self.world.component_for_entity(ability_entity, Ability)
        except KeyError:
            return ""
        parts: list[str] = []
        if ability.description:
            parts.append(ability.description)
        cooldown_lines = self._format_cooldown_details(ability_entity, ability.cooldown)
        if cooldown_lines:
            parts.extend(cooldown_lines)
        return "\n".join(parts)

    def _format_cooldown_details(self, ability_entity: int, base_cooldown: int) -> list[str]:
        details: list[str] = []
        if base_cooldown > 0:
            suffix = "turn" if base_cooldown == 1 else "turns"
            details.append(f"Cooldown: {base_cooldown} {suffix}")
        remaining = self._ability_cooldown_remaining(ability_entity)
        if remaining > 0:
            suffix = "turn" if remaining == 1 else "turns"
            details.append(f"Ready in {remaining} {suffix}")
        return details

    def _ability_cooldown_remaining(self, ability_entity: int) -> int:
        try:
            cooldown = self.world.component_for_entity(ability_entity, AbilityCooldown)
        except KeyError:
            return 0
        return max(0, int(cooldown.remaining_turns))

    def _player_effect_text(self, owner_entity: int) -> str:
        effect_list = self._get_effect_list(owner_entity)
        if effect_list is None or not effect_list.effect_entities:
            return "No active effects"
        lines: list[str] = []
        for effect_entity in list(effect_list.effect_entities):
            try:
                effect = self.world.component_for_entity(effect_entity, Effect)
            except KeyError:
                continue
            label = self._effect_display_name(effect.slug)
            description = self._effect_description(effect)
            meta = self._format_effect_metadata(effect)
            duration_text = self._effect_duration_text(effect_entity)
            parts = [label]
            if description:
                parts.append(description)
            if meta:
                parts.append(meta)
            if duration_text:
                parts.append(duration_text)
            lines.append(" — ".join(parts))
        if not lines:
            return "No active effects"
        if len(lines) == 1:
            return lines[0]
        sorted_lines = sorted(lines)
        formatted = ["Active effects:"] + [f"- {line}" for line in sorted_lines]
        return "\n".join(formatted)

    def _get_effect_list(self, owner_entity: int) -> EffectList | None:
        try:
            return self.world.component_for_entity(owner_entity, EffectList)
        except KeyError:
            return None

    def _effect_display_name(self, slug: str) -> str:
        try:
            definition = default_effect_registry.get(slug)
        except KeyError:
            return slug.replace("_", " ").title()
        if definition.display_name:
            return definition.display_name
        return slug.replace("_", " ").title()

    def _effect_duration_text(self, effect_entity: int) -> str:
        try:
            duration = self.world.component_for_entity(effect_entity, EffectDuration)
        except KeyError:
            return ""
        remaining = max(0, int(duration.remaining_turns))
        if remaining <= 0:
            return "expires soon"
        if remaining == 1:
            return "1 turn remaining"
        return f"{remaining} turns remaining"

    def _format_effect_metadata(self, effect: Effect) -> str:
        metadata = effect.metadata or {}
        if effect.slug == "damage_bonus":
            bonus = metadata.get("bonus")
            if bonus is None:
                bonus_value = None
            else:
                try:
                    bonus_value = float(bonus)
                except (TypeError, ValueError):
                    bonus_value = None
            if bonus_value is not None:
                if bonus_value.is_integer():
                    bonus_value = int(bonus_value)
                return f"+{bonus_value} damage"
        return ""

    def _effect_description(self, effect: Effect) -> str:
        definition = None
        try:
            definition = default_effect_registry.get(effect.slug)
        except KeyError:
            definition = None
        description = ""
        if definition and definition.description:
            description = definition.description
        meta_desc = effect.metadata.get("description") if effect.metadata else None
        if meta_desc:
            try:
                meta_text = str(meta_desc)
            except Exception:
                meta_text = None
            if meta_text:
                return meta_text
        return description