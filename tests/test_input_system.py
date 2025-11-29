from typing import Any

from ecs.events.bus import (
    EventBus,
    EVENT_MOUSE_PRESS,
    EVENT_TILE_CLICK,
    EVENT_BANK_MANA,
)
from ecs.systems.input import InputSystem
from ecs.constants import GRID_ROWS, GRID_COLS, TILE_SIZE, BOTTOM_MARGIN
from world import create_world
from ecs.components.health import Health
from ecs.systems.health_system import HealthSystem

class DummyWindow:
    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height
        self.render_system: Any | None = None


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

    def get_bank_icon_at_point(self, x, y):
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

    bus.subscribe(EVENT_BANK_MANA, on_gain)

    bus.emit(EVENT_MOUSE_PRESS, x=120, y=110, button=1)

    assert gained, "Clicking knowledge bar should grant a secret"
    assert gained[-1]["type_name"] == "secrets"
    assert gained[-1]["amount"] == 1


class PortraitRenderSystem:
    def __init__(self, owner_entity):
        self._owner_entity = owner_entity

    def get_player_panel_at_point(self, x, y):
        return {"owner_entity": self._owner_entity}

    def get_ability_at_point(self, x, y):
        return None

    def get_forbidden_knowledge_at_point(self, x, y):
        return None

    def get_bank_icon_at_point(self, x, y):
        return None


def _human_entity(world):
    from ecs.components.human_agent import HumanAgent

    for entity, _ in world.get_component(HumanAgent):
        return entity
    raise AssertionError("Expected a human agent in the world")


def _enemy_entity(world):
    from ecs.components.rule_based_agent import RuleBasedAgent

    for entity, _ in world.get_component(RuleBasedAgent):
        return entity
    raise AssertionError("Expected an enemy agent in the world")


def test_portrait_click_damages_player():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    HealthSystem(world, bus)
    player_entity = _human_entity(world)

    window = DummyWindow()
    window.render_system = PortraitRenderSystem(player_entity)

    InputSystem(bus, window, world=world)

    health = world.component_for_entity(player_entity, Health)
    starting_hp = health.current

    bus.emit(EVENT_MOUSE_PRESS, x=50, y=50, button=1)

    assert health.current == starting_hp - 10


def test_portrait_click_damages_enemy():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    HealthSystem(world, bus)
    enemy_entity = _enemy_entity(world)

    window = DummyWindow()
    window.render_system = PortraitRenderSystem(enemy_entity)

    InputSystem(bus, window, world=world)

    health = world.component_for_entity(enemy_entity, Health)
    starting_hp = health.current

    bus.emit(EVENT_MOUSE_PRESS, x=75, y=40, button=1)

    assert health.current == starting_hp - 10
