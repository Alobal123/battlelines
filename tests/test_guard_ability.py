from __future__ import annotations

from typing import Dict, Tuple

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.board_position import BoardPosition
from ecs.components.effect import Effect
from ecs.components.effect_list import EffectList
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.tile_status_overlay import TileStatusOverlay
from ecs.events.bus import (
    EVENT_ABILITY_EFFECT_APPLIED,
    EVENT_ABILITY_EXECUTE,
    EVENT_TURN_ACTION_STARTED,
    EventBus,
)
from ecs.systems.ability_resolution_system import AbilityResolutionSystem
from ecs.systems.board import BoardSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.turn_system import TurnSystem
from world import create_world


def _setup_world(rows: int = 4, cols: int = 4) -> tuple[EventBus, World, BoardSystem]:
    bus = EventBus()
    world = create_world(bus)
    EffectLifecycleSystem(world, bus)
    AbilityResolutionSystem(world, bus)
    TurnSystem(world, bus)
    board = BoardSystem(world, bus, rows=rows, cols=cols)
    return bus, world, board


def _mastiffs_and_ability(world: World, ability_name: str) -> tuple[int, int]:
    enemy_pool = getattr(world, "enemy_pool")
    mastiffs = enemy_pool.create_enemy("mastiffs")
    owner = world.component_for_entity(mastiffs, AbilityListOwner)
    for ability_entity in owner.ability_entities:
        ability = world.component_for_entity(ability_entity, Ability)
        if ability.name == ability_name:
            return mastiffs, ability_entity
    raise AssertionError(f"Ability '{ability_name}' not found on mastiffs")


def _guard_mappings(world: World) -> Dict[int, Tuple[int, int]]:
    mapping: Dict[int, Tuple[int, int]] = {}
    for tile_entity, overlay in world.get_component(TileStatusOverlay):
        if overlay.slug != "tile_guarded":
            continue
        try:
            position = world.component_for_entity(tile_entity, BoardPosition)
        except KeyError:
            continue
        mapping[tile_entity] = (position.row, position.col)
    return mapping


def _guard_effects_by_tile(world: World) -> Dict[int, int]:
    guard_effects: Dict[int, int] = {}
    for tile_entity, effect_list in world.get_component(EffectList):
        for effect_entity in list(effect_list.effect_entities):
            try:
                effect = world.component_for_entity(effect_entity, Effect)
            except KeyError:
                continue
            if effect.owner_entity != tile_entity:
                continue
            if effect.slug != "tile_guarded":
                continue
            guard_effects[tile_entity] = effect_entity
    return guard_effects


def _execute_guard(bus: EventBus, world: World, owner_entity: int, ability_entity: int) -> None:
    pending = PendingAbilityTarget(
        ability_entity=ability_entity,
        owner_entity=owner_entity,
        row=None,
        col=None,
        target_entity=owner_entity,
    )
    bus.emit(
        EVENT_TURN_ACTION_STARTED,
        source="ability",
        owner_entity=owner_entity,
        ability_entity=ability_entity,
    )
    bus.emit(
        EVENT_ABILITY_EXECUTE,
        ability_entity=ability_entity,
        owner_entity=owner_entity,
        pending=pending,
    )


def test_guard_places_five_guarded_tiles():
    bus, world, _ = _setup_world(rows=3, cols=4)
    rng = getattr(world, "random", None)
    if rng is not None:
        rng.seed(11)
    mastiffs, guard_ability = _mastiffs_and_ability(world, "guard")

    effect_events: list[dict] = []
    bus.subscribe(
        EVENT_ABILITY_EFFECT_APPLIED,
        lambda sender, **payload: effect_events.append(payload),
    )

    _execute_guard(bus, world, mastiffs, guard_ability)

    guard_tiles = _guard_mappings(world)
    assert len(guard_tiles) == 5, f"Expected five guarded tiles, found {guard_tiles}"

    guard_effects = _guard_effects_by_tile(world)
    assert len(guard_effects) == 5
    for tile_entity, effect_entity in guard_effects.items():
        effect = world.component_for_entity(effect_entity, Effect)
        assert effect.metadata.get("reason") == "guard"
        assert effect.metadata.get("source_owner") == mastiffs

    assert effect_events, "Guard ability should emit ability effect event"
    assert effect_events[-1]["ability_entity"] == guard_ability
    assert set(effect_events[-1]["affected"]) == set(guard_effects.keys())


def test_guard_skips_tiles_with_existing_effects():
    bus, world, _ = _setup_world(rows=3, cols=3)
    rng = getattr(world, "random", None)
    if rng is not None:
        rng.seed(3)
    mastiffs, guard_ability = _mastiffs_and_ability(world, "guard")

    _execute_guard(bus, world, mastiffs, guard_ability)
    first_guard_map = _guard_effects_by_tile(world)
    assert len(first_guard_map) == 5

    if rng is not None:
        rng.seed(3)
    _execute_guard(bus, world, mastiffs, guard_ability)

    second_guard_map = _guard_effects_by_tile(world)
    assert len(second_guard_map) == 9, "All tiles should end up guarded after two uses on a 3x3 board"

    for tile_entity, effect_id in first_guard_map.items():
        assert second_guard_map.get(tile_entity) == effect_id, "Guard should not replace existing guarded tiles"