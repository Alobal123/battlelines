from __future__ import annotations

import random

from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_EFFECT_APPLIED,
    EVENT_ABILITY_EXECUTE,
    EVENT_BOARD_CHANGED,
    EVENT_CASCADE_COMPLETE,
    EVENT_HEALTH_HEAL,
    EVENT_TURN_ACTION_STARTED,
    EVENT_TURN_ADVANCED,
)
from esper import World

from world import create_world
from ecs.components.ability import Ability
from ecs.components.ability_effect import AbilityEffects
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.active_turn import ActiveTurn
from ecs.components.health import Health
from ecs.components.human_agent import HumanAgent
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.tile import TileType
from ecs.components.tile_type_registry import TileTypeRegistry
from ecs.components.tile_types import TileTypes
from ecs.components.turn_order import TurnOrder
from ecs.factories.abilities import create_ability_by_name
from ecs.systems.ability_resolution_system import AbilityResolutionSystem
from ecs.systems.board import BoardSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.board_transform_effect_system import BoardTransformEffectSystem
from ecs.systems.effects.heal_effect_system import HealEffectSystem
from ecs.systems.health_system import HealthSystem
from ecs.systems.turn_system import TurnSystem
from ecs.systems.turn_state_utils import get_or_create_turn_state


def _seed_rng(world: World, seed: int = 1) -> None:
    rng = getattr(world, "random", None)
    if isinstance(rng, random.Random):
        rng.seed(seed)


def _apply_board_layout(world: World, board: BoardSystem, layout: list[list[str]]) -> None:
    for row_idx, row_values in enumerate(layout):
        for col_idx, tile_name in enumerate(row_values):
            entity = board._get_entity_at(row_idx, col_idx)
            assert entity is not None
            tile = world.component_for_entity(entity, TileType)
            tile.type_name = tile_name


def _attach_to_mastiffs(world: World, ability_entity: int) -> int:
    enemy_pool = getattr(world, "enemy_pool")
    mastiffs = enemy_pool.create_enemy("mastiffs")
    owner = world.component_for_entity(mastiffs, AbilityListOwner)
    owner.ability_entities.append(ability_entity)
    return mastiffs


def test_cease_witchfire_definition():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)

    ability_entity = create_ability_by_name(world, "cease_witchfire")
    ability = world.component_for_entity(ability_entity, Ability)
    assert ability.cost == {"shapeshift": 4}
    assert ability.ends_turn is True
    assert "witchfire" in ability.description.lower()

    effects = world.component_for_entity(ability_entity, AbilityEffects)
    assert len(effects.effects) == 2

    transform_spec = effects.effects[0]
    assert transform_spec.slug == "board_transform_type"
    assert transform_spec.target == "board"
    assert transform_spec.metadata.get("reason") == "cease_witchfire"
    assert transform_spec.metadata.get("context_read") == {
        "positions": "cease_witchfire_positions",
        "target_types": "cease_witchfire_target_types",
    }

    heal_spec = effects.effects[1]
    assert heal_spec.slug == "heal"
    assert heal_spec.target == "self"
    assert heal_spec.metadata.get("amount") == 3
    assert heal_spec.metadata.get("reason") == "cease_witchfire"


def test_cease_witchfire_converts_witchfire_and_heals():
    bus = EventBus()
    world = create_world(bus)

    EffectLifecycleSystem(world, bus)
    BoardTransformEffectSystem(world, bus)
    HealEffectSystem(world, bus)
    HealthSystem(world, bus)
    AbilityResolutionSystem(world, bus)

    board = BoardSystem(world, bus, rows=3, cols=3)
    layout = [
        ["witchfire", "witchfire", "witchfire"],
        ["hex", "nature", "blood"],
        ["spirit", "secrets", "shapeshift"],
    ]
    _apply_board_layout(world, board, layout)
    _seed_rng(world, seed=1)

    ability_entity = create_ability_by_name(world, "cease_witchfire")
    mastiffs = _attach_to_mastiffs(world, ability_entity)

    health = world.component_for_entity(mastiffs, Health)
    health.current = max(0, health.current - 5)
    before_health = health.current

    pending = PendingAbilityTarget(
        ability_entity=ability_entity,
        owner_entity=mastiffs,
        row=None,
        col=None,
        target_entity=mastiffs,
    )

    board_events: list[dict] = []
    heal_events: list[dict] = []
    bus.subscribe(EVENT_BOARD_CHANGED, lambda sender, **payload: board_events.append(payload))
    bus.subscribe(EVENT_HEALTH_HEAL, lambda sender, **payload: heal_events.append(payload))

    bus.emit(
        EVENT_ABILITY_EXECUTE,
        ability_entity=ability_entity,
        owner_entity=mastiffs,
        pending=pending,
    )

    assert heal_events, "Cease Witchfire should heal the mastiffs"
    heal_payload = heal_events[-1]
    assert heal_payload["target_entity"] == mastiffs
    assert heal_payload["amount"] == 3
    assert heal_payload.get("reason") == "cease_witchfire"

    expected_health = min(world.component_for_entity(mastiffs, Health).max_hp, before_health + 3)
    assert world.component_for_entity(mastiffs, Health).current == expected_health

    assert board_events, "Cease Witchfire should emit a board change event"
    positions = board_events[-1].get("positions", [])
    assert set(positions) == {(0, 0), (0, 1), (0, 2)}
    typed_entries = board_events[-1].get("types", [])
    assert len(typed_entries) == len(positions)

    registry_entity = next(ent for ent, _ in world.get_component(TileTypeRegistry))
    tile_types: TileTypes = world.component_for_entity(registry_entity, TileTypes)
    valid_types = {name for name in tile_types.spawnable_types() if name != "witchfire"}

    for col in range(3):
        tile_entity = board._get_entity_at(0, col)
        assert tile_entity is not None
        tile = world.component_for_entity(tile_entity, TileType)
        assert tile.type_name in valid_types
        assert tile.type_name != "witchfire"

    for row, col, type_name in typed_entries:
        assert (row, col) in {(0, 0), (0, 1), (0, 2)}
        assert type_name in valid_types

    for row, col in ((1, 0), (2, 1), (2, 2)):
        tile_entity = board._get_entity_at(row, col)
        assert tile_entity is not None
        tile = world.component_for_entity(tile_entity, TileType)
        assert tile.type_name == layout[row][col]


def test_cease_witchfire_advances_turn_to_player():
    bus = EventBus()
    world = create_world(bus)

    EffectLifecycleSystem(world, bus)
    BoardTransformEffectSystem(world, bus)
    HealEffectSystem(world, bus)
    HealthSystem(world, bus)
    AbilityResolutionSystem(world, bus)
    TurnSystem(world, bus)

    ability_events: list[dict] = []
    cascade_events: list[dict] = []
    turn_events: list[dict] = []

    bus.subscribe(EVENT_ABILITY_EFFECT_APPLIED, lambda sender, **payload: ability_events.append(payload))
    bus.subscribe(EVENT_CASCADE_COMPLETE, lambda sender, **payload: cascade_events.append(payload))
    bus.subscribe(EVENT_TURN_ADVANCED, lambda sender, **payload: turn_events.append(payload))

    board = BoardSystem(world, bus, rows=3, cols=3)
    layout = [
        ["witchfire", "witchfire", "witchfire"],
        ["hex", "nature", "blood"],
        ["spirit", "secrets", "shapeshift"],
    ]
    _apply_board_layout(world, board, layout)
    _seed_rng(world, seed=1)

    ability_entity = create_ability_by_name(world, "cease_witchfire")
    mastiffs = _attach_to_mastiffs(world, ability_entity)
    human_entity = next(ent for ent, _ in world.get_component(HumanAgent))

    order_entries = list(world.get_component(TurnOrder))
    assert order_entries
    _, turn_order = order_entries[0]
    turn_order.owners = [human_entity, mastiffs]
    turn_order.index = 1

    pending = PendingAbilityTarget(
        ability_entity=ability_entity,
        owner_entity=mastiffs,
        row=None,
        col=None,
        target_entity=mastiffs,
    )
    world.add_component(ability_entity, pending)

    active_entries = list(world.get_component(ActiveTurn))
    assert active_entries
    _, active_turn = active_entries[0]
    active_turn.owner_entity = mastiffs

    bus.emit(
        EVENT_TURN_ACTION_STARTED,
        source="ability",
        owner_entity=mastiffs,
        ability_entity=ability_entity,
    )

    bus.emit(
        EVENT_ABILITY_EXECUTE,
        ability_entity=ability_entity,
        owner_entity=mastiffs,
        pending=pending,
    )

    active_after = list(world.get_component(ActiveTurn))[0][1].owner_entity
    state = get_or_create_turn_state(world)
    assert ability_events, "Cease Witchfire should emit ability effect signal"
    assert cascade_events, "Cease Witchfire should emit cascade completion"
    assert turn_events, "TurnSystem should advance after Cease Witchfire resolves"
    assert state.cascade_observed is False
    assert active_after == human_entity
