import random

from ecs.events.bus import (
    EventBus,
    EVENT_ENEMY_POOL_OFFER,
    EVENT_ENEMY_POOL_REQUEST,
)
from ecs.factories.enemies import create_enemy_undead_gardener
from ecs.systems.enemy_pool_system import EnemyPoolSystem
from ecs.world import create_world


def test_enemy_pool_offers_unique_names():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    rng = random.Random(1)
    pool = EnemyPoolSystem(world, bus, rng=rng)
    assert "undead_florist" in pool.known_enemy_names()
    captured = {}
    bus.subscribe(EVENT_ENEMY_POOL_OFFER, lambda s, **p: captured.update(p))

    bus.emit(EVENT_ENEMY_POOL_REQUEST, count=2, request_id="req")

    assert captured.get("request_id") == "req"
    offers = captured.get("enemies")
    assert offers is not None
    assert len(offers) == min(2, len(pool.known_enemy_names()))
    assert len(set(offers)) == len(offers)


def test_enemy_pool_spawn_random_enemy():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    rng = random.Random(2)
    pool = EnemyPoolSystem(world, bus, rng=rng)

    # clear existing enemy to isolate spawn
    from ecs.components.rule_based_agent import RuleBasedAgent

    for entity, _ in list(world.get_component(RuleBasedAgent)):
        world.delete_entity(entity)

    enemy_entity = pool.spawn_random_enemy()
    if pool.known_enemy_names():
        assert enemy_entity is not None
        assert any(ent == enemy_entity for ent, _ in world.get_component(RuleBasedAgent))
    else:
        assert enemy_entity is None
