from typing import Any

from ecs.events.bus import (
    EventBus,
    EVENT_MOUSE_PRESS,
    EVENT_TILE_CLICK,
    EVENT_TILE_BANK_GAINED,
    EVENT_GAME_MODE_CHANGED,
)
from ecs.systems.input import InputSystem, DEFAULT_TRANSITION_GUARD
from ecs.constants import GRID_ROWS, GRID_COLS, TILE_SIZE, BOTTOM_MARGIN
from ecs.world import create_world
from ecs.components.game_state import GameMode

class DummyWindow:
    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height
        self.render_system: Any | None = None


class _FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def advance(self, delta: float) -> None:
        self.value += delta

    def __call__(self) -> float:
        return self.value


def test_mouse_press_translates_to_tile_click():
    bus = EventBus()
    window = DummyWindow()
    input_system = InputSystem(bus, window)
    received = {}
    def handler(sender, **kwargs):
        received.update(kwargs)
    bus.subscribe(EVENT_TILE_CLICK, handler)
    pressed = {}
    def press_handler(sender, **kwargs):
        pressed.update(kwargs)
    bus.subscribe(EVENT_MOUSE_PRESS, press_handler)
    # Click inside first cell (row0,col0)
    x = (window.width - GRID_COLS * TILE_SIZE)/2 + TILE_SIZE/2 + 1
    y = BOTTOM_MARGIN + TILE_SIZE/2 + 1
    bus.emit(EVENT_MOUSE_PRESS, x=x, y=y, button=1)
    assert pressed.get('x') == x
    assert pressed.get('y') == y
    assert received.get('row') == 0
    assert received.get('col') == 0


class DummyRenderSystem:
    def __init__(self, target_rect):
        self._rect = target_rect

    def get_ability_at_point(self, x, y):
        return None

    def get_forbidden_knowledge_at_point(self, x, y):
        left, bottom, width, height = self._rect
        if left <= x <= left + width and bottom <= y <= bottom + height:
            return {"entity": 1}
        return None


def test_knowledge_bar_click_grants_secret():
    bus = EventBus()
    world = create_world(bus)
    window = DummyWindow()
    window.render_system = DummyRenderSystem(target_rect=(100, 100, 200, 20))

    input_system = InputSystem(bus, window, world=world)

    gained = []

    def on_gain(sender, **payload):
        gained.append(payload)

    bus.subscribe(EVENT_TILE_BANK_GAINED, on_gain)

    bus.emit(EVENT_MOUSE_PRESS, x=120, y=110, button=1)

    assert gained, "Clicking knowledge bar should grant a secret"
    assert gained[-1]["type_name"] == "secrets"
    assert gained[-1]["amount"] == 1


def test_mouse_press_ignored_immediately_after_mode_change():
    bus = EventBus()
    world = create_world(bus)
    window = DummyWindow()
    clock = _FakeClock()
    input_system = InputSystem(bus, window, world=world, clock=clock)

    clicks = []

    bus.subscribe(EVENT_TILE_CLICK, lambda sender, **payload: clicks.append(payload))

    x = (window.width - GRID_COLS * TILE_SIZE)/2 + TILE_SIZE/2 + 1
    y = BOTTOM_MARGIN + TILE_SIZE/2 + 1

    # Initial click registers normally
    bus.emit(EVENT_MOUSE_PRESS, x=x, y=y, button=1, press_id=10)
    assert len(clicks) == 1

    # Rapid mode change after the click triggers guard
    clock.advance(0.01)
    bus.emit(
        EVENT_GAME_MODE_CHANGED,
        previous_mode=GameMode.DIALOGUE,
        new_mode=GameMode.COMBAT,
        input_guard_press_id=10,
        input_guard_interval=0.0,
    )

    bus.emit(EVENT_MOUSE_PRESS, x=x, y=y, button=1, press_id=10)
    assert len(clicks) == 1, "Second click should be ignored during guard interval"

    clock.advance(DEFAULT_TRANSITION_GUARD)
    bus.emit(EVENT_MOUSE_PRESS, x=x, y=y, button=1, press_id=11)
    assert len(clicks) == 2, "Click after guard expires should register"
