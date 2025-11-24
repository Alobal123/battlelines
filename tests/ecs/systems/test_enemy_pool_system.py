import random

from ecs.events.bus import (
    EventBus,
    EVENT_ENEMY_POOL_OFFER,
    EVENT_ENEMY_POOL_REQUEST,
)
from ecs.factories.enemies import create_enemy_undead_gardener
from ecs.systems.enemy_pool_system import EnemyPoolSystem
from world import create_world


def test_enemy_pool_offers_unique_names():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    rng = random.Random(1)
    pool = EnemyPoolSystem(world, bus, rng=rng)
    names = set(pool.known_enemy_names())
    assert {"undead_florist", "undead_beekeeper"}.issubset(names)
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


def test_enemy_pool_avoids_immediate_repeat():
    class StaticRandom(random.Random):
        def __init__(self):
            super().__init__()

        def choice(self, seq):
            # Always return the lexicographically highest value to stress the fallback path.
            return seq[-1]

        def shuffle(self, seq):
            # Leave sequence order intact.
            return None

    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    pool = EnemyPoolSystem(world, bus, rng=StaticRandom())

    from ecs.components.rule_based_agent import RuleBasedAgent
    from ecs.components.character import Character

    # Remove default enemy for clean slate.
    for entity, _ in list(world.get_component(RuleBasedAgent)):
        world.delete_entity(entity)

    first_enemy = pool.spawn_random_enemy()
    first_slug = world.component_for_entity(first_enemy, Character).slug if first_enemy is not None else None

    second_enemy = pool.spawn_random_enemy()
    second_slug = world.component_for_entity(second_enemy, Character).slug if second_enemy is not None else None

    if len(pool.known_enemy_names()) > 1:
        assert first_slug is not None
        assert second_slug is not None
        assert first_slug != second_slug
