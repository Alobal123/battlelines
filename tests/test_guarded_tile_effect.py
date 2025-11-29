from __future__ import annotations

import pytest

from ecs.events.bus import EVENT_EFFECT_APPLY, EVENT_MATCH_CLEARED, EventBus
from ecs.components.active_switch import ActiveSwitch
from ecs.components.effect import Effect
from ecs.components.effect_list import EffectList
from ecs.components.health import Health
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.tile_status_overlay import TileStatusOverlay
from ecs.systems.board import BoardSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.damage_effect_system import DamageEffectSystem
from ecs.systems.effects.guarded_tile_effect_system import GuardedTileEffectSystem
from ecs.systems.effects.tile_sacrifice_effect_system import TileSacrificeEffectSystem
from ecs.systems.effects.tile_status_system import TileStatusSystem
from ecs.systems.health_system import HealthSystem
from world import create_world
from ecs.systems.board_ops import (
    apply_gravity_moves,
    clear_tiles_with_cascade,
    compute_gravity_moves,
    snapshot_tile_entities,
)
from ecs.components.tile import TileType


def _setup_world(rows: int = 2, cols: int = 2):
    bus = EventBus()
    world = create_world(bus)
    EffectLifecycleSystem(world, bus)
    DamageEffectSystem(world, bus)
    HealthSystem(world, bus)
    GuardedTileEffectSystem(world, bus)
    board = BoardSystem(world, bus, rows=rows, cols=cols)
    return bus, world, board


def _tile_entity(board: BoardSystem, row: int, col: int) -> int:
    entity = board._get_entity_at(row, col)
    assert entity is not None
    return entity


def _human_entity(world):
    return next(ent for ent, _ in world.get_component(HumanAgent))


def _enemy_entity(world):
    return next(ent for ent, _ in world.get_component(RuleBasedAgent))


def _guard_effect_ids(world, tile_entity: int) -> list[int]:
    try:
        effect_list: EffectList = world.component_for_entity(tile_entity, EffectList)
    except KeyError:
        return []
    guard_ids: list[int] = []
    for effect_id in list(effect_list.effect_entities):
        try:
            effect = world.component_for_entity(effect_id, Effect)
        except KeyError:
            continue
        if effect.slug == "tile_guarded":
            guard_ids.append(effect_id)
    return guard_ids


def test_guarded_tile_damages_opponent_on_match():
    bus, world, board = _setup_world()
    player = _human_entity(world)
    opponent = _enemy_entity(world)
    tile_entity = _tile_entity(board, 0, 0)

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=tile_entity,
        slug="tile_guarded",
        metadata={"source_owner": player},
    )

    opponent_health = world.component_for_entity(opponent, Health)
    before = opponent_health.current

    bus.emit(
        EVENT_MATCH_CLEARED,
        positions=[(0, 0)],
        types=[(0, 0, "blood")],
        owner_entity=opponent,
    )

    assert world.component_for_entity(opponent, Health).current == before - 1
    assert not _guard_effect_ids(world, tile_entity)
    with pytest.raises(KeyError):
        world.component_for_entity(tile_entity, TileStatusOverlay)


def test_guarded_tile_ignored_for_owner_match():
    bus, world, board = _setup_world()
    player = _human_entity(world)
    tile_entity = _tile_entity(board, 0, 1)

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=tile_entity,
        slug="tile_guarded",
        metadata={"source_owner": player},
    )

    before = world.component_for_entity(player, Health).current

    bus.emit(
        EVENT_MATCH_CLEARED,
        positions=[(0, 1)],
        types=[(0, 1, "blood")],
        owner_entity=player,
    )

    assert world.component_for_entity(player, Health).current == before
    guard_effects = _guard_effect_ids(world, tile_entity)
    assert guard_effects, "Guarded effect should persist when owner matches the tile"


def test_guarded_tile_triggers_on_sacrifice_and_overlay_removed():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    board = BoardSystem(world, bus, rows=2, cols=2)
    EffectLifecycleSystem(world, bus)
    DamageEffectSystem(world, bus)
    HealthSystem(world, bus)
    TileStatusSystem(world, bus)
    TileSacrificeEffectSystem(world, bus)

    attacker = _human_entity(world)
    defender = _enemy_entity(world)
    tile_entity = _tile_entity(board, 1, 0)

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=tile_entity,
        slug="tile_guarded",
        metadata={"source_owner": defender},
    )

    before = world.component_for_entity(attacker, Health).current

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=board.board_entity,
        slug="tile_sacrifice",
        metadata={
            "origin_row": 1,
            "origin_col": 0,
            "source_owner": attacker,
        },
    )

    after = world.component_for_entity(attacker, Health).current
    assert after == before - 1
    with pytest.raises(KeyError):
        world.component_for_entity(tile_entity, TileStatusOverlay)


def test_guarded_tile_effect_follows_gravity():
    bus, world, board = _setup_world(rows=2, cols=1)
    TileStatusSystem(world, bus)

    owner = _human_entity(world)
    lower_entity = _tile_entity(board, 0, 0)
    upper_entity = _tile_entity(board, 1, 0)

    lower_switch: ActiveSwitch = world.component_for_entity(lower_entity, ActiveSwitch)
    lower_switch.active = False

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=upper_entity,
        slug="tile_guarded",
        metadata={"source_owner": owner},
    )

    guard_ids_top = _guard_effect_ids(world, upper_entity)
    assert guard_ids_top, "Effect should attach to the original tile"

    moves, _ = compute_gravity_moves(world)
    assert moves, "Expected gravity to move the guarded tile"

    apply_gravity_moves(world, moves)

    assert not _guard_effect_ids(world, upper_entity), "Source tile should lose its effect"
    guard_ids_bottom = _guard_effect_ids(world, lower_entity)
    assert guard_ids_bottom, "Destination tile should inherit tile effects"

    overlay = world.component_for_entity(lower_entity, TileStatusOverlay)
    assert overlay.slug == "tile_guarded"
    assert overlay.effect_entity in guard_ids_bottom

    for effect_id in guard_ids_bottom:
        effect = world.component_for_entity(effect_id, Effect)
        assert effect.owner_entity == lower_entity

    with pytest.raises(KeyError):
        world.component_for_entity(upper_entity, TileStatusOverlay)


def test_guarded_tile_persists_when_match_occurs_below():
    bus, world, board = _setup_world(rows=4, cols=1)
    TileStatusSystem(world, bus)

    owner = _human_entity(world)
    guard_entity = _tile_entity(board, 3, 0)

    # Ensure a vertical match directly below the guarded tile.
    for row in range(3):
        entity = _tile_entity(board, row, 0)
        world.component_for_entity(entity, TileType).type_name = "nature"
    world.component_for_entity(guard_entity, TileType).type_name = "blood"

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=guard_entity,
        slug="tile_guarded",
        metadata={"source_owner": owner},
    )

    match_positions = [(0, 0), (1, 0), (2, 0)]
    snapshot = snapshot_tile_entities(world, match_positions)
    _, typed, _, _, _ = clear_tiles_with_cascade(world, match_positions)

    bus.emit(
        EVENT_MATCH_CLEARED,
        positions=match_positions,
        types=typed,
        owner_entity=_enemy_entity(world),
        entities=snapshot,
    )

    remaining = [effect for _, effect in world.get_component(Effect) if effect.slug == "tile_guarded"]
    assert remaining, "Guarded effect should persist when only adjacent tiles were cleared"


def test_guarded_tile_survives_event_before_gravity_transfer():
    bus, world, board = _setup_world(rows=4, cols=1)
    TileStatusSystem(world, bus)

    owner = _human_entity(world)
    opponent = _enemy_entity(world)
    guard_entity = _tile_entity(board, 3, 0)

    for row in range(3):
        entity = _tile_entity(board, row, 0)
        world.component_for_entity(entity, TileType).type_name = "nature"
    world.component_for_entity(guard_entity, TileType).type_name = "blood"

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=guard_entity,
        slug="tile_guarded",
        metadata={"source_owner": owner},
    )

    match_positions = [(0, 0), (1, 0), (2, 0)]
    snapshot = snapshot_tile_entities(world, match_positions)
    _, typed, moves, _, _ = clear_tiles_with_cascade(
        world,
        match_positions,
        apply_gravity=False,
    )

    assert moves, "Expected gravity moves so guarded tile will fall"

    bus.emit(
        EVENT_MATCH_CLEARED,
        positions=match_positions,
        types=typed,
        owner_entity=opponent,
        entities=snapshot,
    )

    guard_ids = _guard_effect_ids(world, guard_entity)
    assert guard_ids, "Effect should remain on original tile before gravity"

    apply_gravity_moves(world, moves)

    bottom_entity = _tile_entity(board, 0, 0)
    assert _guard_effect_ids(world, bottom_entity), "Effect should transfer after gravity"