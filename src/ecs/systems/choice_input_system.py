"""Input system that handles interactions with the choice window."""
from __future__ import annotations

from esper import World

from ecs.events.bus import (
    EventBus,
    EVENT_MOUSE_PRESS,
    EVENT_CHOICE_SELECTED,
    EVENT_CHOICE_SKIPPED,
    EVENT_GAME_MODE_CHANGED,
)
from ecs.components.choice_window import ChoiceWindow, ChoiceOption
from ecs.components.game_state import GameMode, GameState


class ChoiceInputSystem:
    """Listens for clicks while a choice window is active and emits results."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self._press_guard_id: int | None = None
        self.event_bus.subscribe(EVENT_MOUSE_PRESS, self.on_mouse_press)
        self.event_bus.subscribe(EVENT_GAME_MODE_CHANGED, self._on_game_mode_changed)

    # Public helper used by tests or simulated input paths
    def handle_mouse_press(
        self,
        x: float,
        y: float,
        button: int,
        press_id: int | None = None,
    ) -> None:
        if button != 1:
            return
        if self._consume_guard(press_id):
            return
        window_data = self._active_window()
        if window_data is None:
            return
        window_entity, window = window_data
        # Check options in order
        for choice_entity, choice in self._options_for_window(window_entity):
            bounds = choice.bounds
            if not bounds:
                continue
            left, bottom, width, height = bounds
            if left <= x <= left + width and bottom <= y <= bottom + height:
                payload = {
                    "window_entity": window_entity,
                    "choice_entity": choice_entity,
                    "payload_entity": choice.payload_entity,
                }
                if press_id is not None:
                    payload["press_id"] = press_id
                self.event_bus.emit(EVENT_CHOICE_SELECTED, **payload)
                return
        if window.skippable and window.skip_button_bounds:
            left, bottom, width, height = window.skip_button_bounds
            if left <= x <= left + width and bottom <= y <= bottom + height:
                payload = {"window_entity": window_entity}
                if press_id is not None:
                    payload["press_id"] = press_id
                self.event_bus.emit(EVENT_CHOICE_SKIPPED, **payload)

    def on_mouse_press(self, sender, **payload):
        x = payload.get("x")
        y = payload.get("y")
        button = payload.get("button")
        if x is None or y is None or button is None:
            return
        press_id = payload.get("press_id")
        try:
            press_id_int = int(press_id) if press_id is not None else None
        except (TypeError, ValueError):
            press_id_int = None
        self.handle_mouse_press(float(x), float(y), int(button), press_id_int)

    def _on_game_mode_changed(self, sender, **payload) -> None:
        new_mode = payload.get("new_mode")
        guard = payload.get("input_guard_press_id")
        if new_mode not in (
            GameMode.COMBAT,
            GameMode.ABILITY_DRAFT,
            GameMode.SKILL_DRAFT,
            GameMode.LOCATION_DRAFT,
        ):
            self._press_guard_id = None
            return
        try:
            self._press_guard_id = int(guard) if guard is not None else None
        except (TypeError, ValueError):
            self._press_guard_id = None

    def _consume_guard(self, press_id: int | None) -> bool:
        guard = self._press_guard_id
        if guard is None:
            return False
        self._press_guard_id = None
        return press_id == guard

    def _options_for_window(self, window_entity: int):
        options = [
            (ent, comp)
            for ent, comp in self.world.get_component(ChoiceOption)
            if comp.window_entity == window_entity
        ]
        options.sort(key=lambda pair: pair[1].order)
        return options

    def _active_window(self):
        if not self._interaction_enabled():
            return None
        windows = list(self.world.get_component(ChoiceWindow))
        if not windows:
            return None
        return windows[0]

    def _interaction_enabled(self) -> bool:
        states = list(self.world.get_component(GameState))
        if not states:
            return True
        mode = states[0][1].mode
        return mode in (
            GameMode.COMBAT,
            GameMode.ABILITY_DRAFT,
            GameMode.SKILL_DRAFT,
            GameMode.LOCATION_DRAFT,
        )
