from ecs.events.bus import (
    EventBus,
    EVENT_EFFECT_APPLY,
    EVENT_HEALTH_DAMAGE,
    EVENT_TURN_ADVANCED,
)
from world import create_world
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.health import Health
from ecs.components.effect import Effect
from ecs.components.effect_list import EffectList
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.poison_effect_system import PoisonEffectSystem
from ecs.systems.health_system import HealthSystem


def _find_human(world):
    return next(ent for ent, _ in world.get_component(HumanAgent))


def _find_enemy(world):
    return next(ent for ent, _ in world.get_component(RuleBasedAgent))


def test_poison_deals_one_damage_and_counts_down():
    bus = EventBus()
    world = create_world(bus)
    EffectLifecycleSystem(world, bus)
    PoisonEffectSystem(world, bus)
    HealthSystem(world, bus)

    human = _find_human(world)

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=human,
        slug="poison",
        metadata={"count": 3},
    )

    captured = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda sender, **payload: captured.append(payload))

    for expected_count in (3, 2, 1):
        bus.emit(EVENT_TURN_ADVANCED, previous_owner=None, new_owner=human)
        assert captured, "Poison should deal damage each afflicted turn"
        payload = captured[-1]
        assert payload["target_entity"] == human
        assert payload["amount"] == 1
        assert payload["reason"] == "poison"
        assert payload.get("source_owner") is None
        effect_list = world.component_for_entity(human, EffectList)
        if effect_list.effect_entities:
            effect_entity = effect_list.effect_entities[0]
            effect = world.component_for_entity(effect_entity, Effect)
            assert effect.count == expected_count - 1

    health = world.component_for_entity(human, Health)
    assert health.current == health.max_hp - 3

    effect_list = world.component_for_entity(human, EffectList)
    assert not effect_list.effect_entities


def test_poison_damage_scales_with_stacks():
    bus = EventBus()
    world = create_world(bus)
    EffectLifecycleSystem(world, bus)
    PoisonEffectSystem(world, bus)
    HealthSystem(world, bus)

    human = _find_human(world)

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=human,
        slug="poison",
        metadata={"count": 12},
    )

    captured: list[int] = []
    bus.subscribe(
        EVENT_HEALTH_DAMAGE,
        lambda sender, **payload: captured.append(payload.get("amount", 0)),
    )

    expected = [1 + n // 5 for n in (12, 11, 10, 9, 8, 7, 6, 5)]
    for remaining in (12, 11, 10, 9, 8, 7, 6, 5):
        bus.emit(EVENT_TURN_ADVANCED, previous_owner=None, new_owner=human)
        assert captured, "Poison should trigger each tick"
        assert captured[-1] == 1 + remaining // 5

    health = world.component_for_entity(human, Health)
    assert health.current == health.max_hp - sum(expected)


def test_poison_accumulates_with_additional_applications():
    bus = EventBus()
    world = create_world(bus)
    EffectLifecycleSystem(world, bus)
    PoisonEffectSystem(world, bus)
    HealthSystem(world, bus)

    human = _find_human(world)

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=human,
        slug="poison",
        metadata={"count": 4},
    )

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=human,
        slug="poison",
        metadata={"count": 6},
    )

    effect_list = world.component_for_entity(human, EffectList)
    assert len(effect_list.effect_entities) == 1
    effect_entity = effect_list.effect_entities[0]
    effect = world.component_for_entity(effect_entity, Effect)
    assert effect.count == 10

    bus.emit(EVENT_TURN_ADVANCED, previous_owner=None, new_owner=human)

    effect = world.component_for_entity(effect_entity, Effect)
    assert effect.count == 9
