from __future__ import annotations

from typing import Any

from ecs.events.bus import (
    EVENT_MOUSE_PRESS,
    EVENT_MOUSE_PRESS_RAW,
    EventBus,
)
from ecs.utils.input_throttle import MouseThrottle


class MouseThrottleSystem:
    """Bridges raw mouse input to throttled events shared by all systems."""

    def __init__(
        self,
        event_bus: EventBus,
        *,
        throttle: MouseThrottle | None = None,
    ) -> None:
        self.event_bus = event_bus
        self._throttle = throttle or MouseThrottle()
        self.event_bus.subscribe(EVENT_MOUSE_PRESS_RAW, self._on_mouse_press_raw)

    @property
    def throttle(self) -> MouseThrottle:
        return self._throttle

    def _on_mouse_press_raw(self, sender: Any, **payload: Any) -> None:
        x = payload.get("x")
        y = payload.get("y")
        button = payload.get("button")
        if x is None or y is None or button is None:
            return
        try:
            xf = float(x)
            yf = float(y)
            button_int = int(button)
        except (TypeError, ValueError):
            return
        if not self._throttle.allow(xf, yf, button_int):
            return
        sanitized = dict(payload)
        sanitized["x"] = xf
        sanitized["y"] = yf
        sanitized["button"] = button_int
        press_id = self._throttle.last_sequence
        if press_id is not None:
            sanitized.setdefault("press_id", press_id)
        self.event_bus.emit(EVENT_MOUSE_PRESS, **sanitized)

