from __future__ import annotations

import pytest

from ecs.events.bus import EVENT_EFFECT_APPLY, EVENT_MATCH_CLEARED, EventBus
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


def _setup_world():
    bus = EventBus()
    world = create_world(bus)
    EffectLifecycleSystem(world, bus)
    DamageEffectSystem(world, bus)
    HealthSystem(world, bus)
    GuardedTileEffectSystem(world, bus)
    board = BoardSystem(world, bus, rows=2, cols=2)
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