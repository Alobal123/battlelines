from ecs.events.bus import (
    EventBus,
    EVENT_EFFECT_APPLY,
    EVENT_HEALTH_DAMAGE,
    EVENT_TURN_ADVANCED,
)
from ecs.world import create_world
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.health import Health
from ecs.components.effect_list import EffectList
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.poison_effect_system import PoisonEffectSystem
from ecs.systems.health_system import HealthSystem


def _find_human(world):
    return next(ent for ent, _ in world.get_component(HumanAgent))


def _find_enemy(world):
    return next(ent for ent, _ in world.get_component(RuleBasedAgent))


def test_poison_deals_damage_at_turn_start():
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
        metadata={"amount": 2},
        turns=3,
        refresh=True,
    )

    captured = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda sender, **payload: captured.append(payload))

    bus.emit(EVENT_TURN_ADVANCED, previous_owner=None, new_owner=human)

    assert captured, "Poison should deal damage at turn start"
    payload = captured[-1]
    assert payload["target_entity"] == human
    assert payload["amount"] == 2
    assert payload["reason"] == "poison"
    assert payload.get("source_owner") is None
    health = world.component_for_entity(human, Health)
    assert health.current == health.max_hp - 2


def test_poison_expires_after_duration():
    bus = EventBus()
    world = create_world(bus)
    EffectLifecycleSystem(world, bus)
    PoisonEffectSystem(world, bus)
    HealthSystem(world, bus)

    human = _find_human(world)
    enemy = _find_enemy(world)

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=human,
        slug="poison",
        metadata={"amount": 3},
        turns=1,
        refresh=True,
    )

    damage_events = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda sender, **payload: damage_events.append(payload))

    bus.emit(EVENT_TURN_ADVANCED, previous_owner=None, new_owner=human)
    first_health = world.component_for_entity(human, Health).current

    bus.emit(EVENT_TURN_ADVANCED, previous_owner=human, new_owner=enemy)

    bus.emit(EVENT_TURN_ADVANCED, previous_owner=enemy, new_owner=human)

    second_health = world.component_for_entity(human, Health).current
    assert first_health == second_health
    assert len(damage_events) == 1

    effect_list = world.component_for_entity(human, EffectList)
    assert not effect_list.effect_entities
