from ecs.events.bus import (
    EventBus,
    EVENT_TILE_BANK_CHANGED,
)
from ecs.world import create_world
from ecs.components.tile_bank import TileBank
from ecs.components.human_agent import HumanAgent
from ecs.systems.input import InputSystem
from ecs.systems.tile_bank_system import TileBankSystem


def _find_human_entity(world):
    return next(ent for ent, _ in world.get_component(HumanAgent))


def _find_bank_entity(world, owner_entity: int) -> tuple[int, TileBank]:
    for entity, bank in world.get_component(TileBank):
        if bank.owner_entity == owner_entity:
            return entity, bank
    raise AssertionError(f"Bank for owner {owner_entity} not found")


def test_bank_click_grants_mana():
    bus = EventBus()
    world = create_world(bus)

    TileBankSystem(world, bus)

    human_ent = _find_human_entity(world)
    bank_ent, bank = _find_bank_entity(world, human_ent)

    class StubRenderSystem:
        def __init__(self, entry):
            self._entry = entry

        def get_ability_at_point(self, x, y):
            return None

        def get_bank_icon_at_point(self, x, y):
            return self._entry

    class StubWindow:
        def __init__(self, render_system):
            self.width = 800
            self.height = 600
            self.render_system = render_system

    entry = {
        "owner_entity": human_ent,
        "bank_entity": bank_ent,
        "type_name": "nature",
        "center_x": 120.0,
        "center_y": 300.0,
        "radius": 32.0,
    }

    window = StubWindow(StubRenderSystem(entry))
    input_system = InputSystem(bus, window, world)

    changed_events = []
    bus.subscribe(
        EVENT_TILE_BANK_CHANGED,
        lambda sender, **payload: changed_events.append(payload),
    )

    initial = bank.counts.get("nature", 0)

    input_system.on_mouse_press(None, x=entry["center_x"], y=entry["center_y"], button=1)

    assert bank.counts.get("nature", 0) == initial + 1
    assert changed_events, "Expected tile bank change event after bank click"
    last_payload = changed_events[-1]
    assert last_payload["entity"] == bank_ent
    assert last_payload["counts"].get("nature", 0) == initial + 1
