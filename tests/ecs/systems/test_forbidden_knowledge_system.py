import random

from ecs.events.bus import (
    EventBus,
    EVENT_TILES_MATCHED,
    EVENT_FORBIDDEN_KNOWLEDGE_CHANGED,
    EVENT_TILE_BANK_CHANGED,
)
from ecs.systems.forbidden_knowledge_system import ForbiddenKnowledgeSystem
from world import create_world
from ecs.components.forbidden_knowledge import ForbiddenKnowledge
from ecs.systems.board import BoardSystem
from ecs.systems.board_ops import get_tile_registry, set_spawnable_tile_types
from ecs.components.tile import TileType
from ecs.components.tile_bank import TileBank
from ecs.components.ability_list_owner import AbilityListOwner


def _fetch_meter(world):
    entries = list(world.get_component(ForbiddenKnowledge))
    assert entries, "ForbiddenKnowledge component expected"
    return entries[0][1], entries[0][0]


def test_forbidden_knowledge_increments_on_secrets_match():
    bus = EventBus()
    world = create_world(bus)
    ForbiddenKnowledgeSystem(world, bus)

    captured = []
    bus.subscribe(EVENT_FORBIDDEN_KNOWLEDGE_CHANGED, lambda sender, **payload: captured.append(payload))

    bus.emit(
        EVENT_TILES_MATCHED,
        positions=[(0, 0), (0, 1), (0, 2)],
        types=[(0, 0, "secrets"), (0, 1, "blood"), (0, 2, "secrets")],
    )

    meter, _ = _fetch_meter(world)
    assert meter.value == 2
    assert captured, "expected forbidden knowledge change event"
    assert captured[-1]["value"] == 2
    assert captured[-1]["delta"] == 2


def test_forbidden_knowledge_caps_at_maximum():
    bus = EventBus()
    world = create_world(bus)
    ForbiddenKnowledgeSystem(world, bus)

    meter, _ = _fetch_meter(world)
    meter.value = meter.max_value - 1

    captured = []
    bus.subscribe(EVENT_FORBIDDEN_KNOWLEDGE_CHANGED, lambda sender, **payload: captured.append(payload))

    bus.emit(
        EVENT_TILES_MATCHED,
        positions=[(1, 0), (1, 1)],
        types=[(1, 0, "secrets"), (1, 1, "secrets")],
    )

    assert meter.value == meter.max_value
    assert captured, "expected forbidden knowledge change event"
    assert captured[-1]["value"] == meter.max_value
    assert captured[-1]["delta"] == 1


def test_chaos_release_converts_board_and_banks():
    random.seed(42)
    bus = EventBus()
    world = create_world(bus)
    set_spawnable_tile_types(world, ["secrets"])
    BoardSystem(world, bus, rows=2, cols=2)
    ForbiddenKnowledgeSystem(world, bus)

    # Preload bank inventory with secrets to verify conversion.
    for _, bank in world.get_component(TileBank):
        bank.counts["secrets"] = bank.counts.get("secrets", 0) + 3

    meter, _ = _fetch_meter(world)
    meter.value = meter.max_value - 1

    bank_updates = []
    bus.subscribe(EVENT_TILE_BANK_CHANGED, lambda sender, **payload: bank_updates.append(payload))

    bus.emit(
        EVENT_TILES_MATCHED,
        positions=[(0, 0)],
        types=[(0, 0, "secrets")],
    )

    assert meter.chaos_released, "chaos release should trigger at maximum meter"
    registry = get_tile_registry(world)
    spawnable = registry.spawnable_types()
    assert "chaos" in spawnable
    assert "secrets" not in spawnable
    tile_types = {tile.type_name for _, tile in world.get_component(TileType)}
    assert "chaos" in tile_types
    assert "secrets" not in tile_types
    for _, bank in world.get_component(TileBank):
        assert bank.counts.get("secrets", 0) == 0
        assert bank.counts.get("chaos", 0) >= 3
    assert bank_updates, "expected bank change events after chaos conversion"


def test_knowledge_bar_gain_increments_meter():
    bus = EventBus()
    world = create_world(bus)
    ForbiddenKnowledgeSystem(world, bus)

    owner = next(ent for ent, _ in world.get_component(AbilityListOwner))

    meter, _ = _fetch_meter(world)
    captured = []
    bus.subscribe(EVENT_FORBIDDEN_KNOWLEDGE_CHANGED, lambda sender, **payload: captured.append(payload))

    bus.emit(
        EVENT_TILE_BANK_CHANGED,
        entity=-1,
        owner_entity=owner,
        counts={},
        delta={"secrets": 2},
        source="knowledge_bar_click",
    )

    assert meter.value == 2
    assert captured, "expected meter change event from knowledge bar grant"
    assert captured[-1]["delta"] == 2
