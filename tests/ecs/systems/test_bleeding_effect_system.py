from ecs.events.bus import (
    EventBus,
    EVENT_EFFECT_APPLY,
    EVENT_HEALTH_DAMAGE,
    EVENT_TILES_MATCHED,
    EVENT_TILE_BANK_CHANGED,
)
from world import create_world
from ecs.components.effect import Effect
from ecs.components.effect_list import EffectList
from ecs.components.health import Health
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.bleeding_effect_system import BleedingEffectSystem
from ecs.systems.health_system import HealthSystem
from ecs.systems.tile_bank_system import TileBankSystem


def _find_human(world):
    return next(ent for ent, _ in world.get_component(HumanAgent))


def _find_enemy(world):
    return next(ent for ent, _ in world.get_component(RuleBasedAgent))


def _emit_bank_gain(bus: EventBus, owner: int, *, type_name: str = "blood", amount: int = 0, source: str = "test") -> None:
    bus.emit(
        EVENT_TILE_BANK_CHANGED,
        entity=-1,
        owner_entity=owner,
        counts={},
        delta={type_name: amount},
        source=source,
    )


def test_bleeding_deals_damage_when_source_gains_blood():
    bus = EventBus()
    world = create_world(bus)
    EffectLifecycleSystem(world, bus)
    BleedingEffectSystem(world, bus)
    HealthSystem(world, bus)

    human = _find_human(world)
    enemy = _find_enemy(world)

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=human,
        slug="bleeding",
        metadata={"count": 7, "source_owner": enemy},
    )

    captured = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda sender, **payload: captured.append(payload))

    _emit_bank_gain(bus, enemy, amount=5)

    assert captured, "Bleeding should trigger on blood gains"
    payload = captured[-1]
    assert payload["target_entity"] == human
    assert payload["amount"] == 5
    assert payload.get("reason") == "bleeding"

    effect_list = world.component_for_entity(human, EffectList)
    effect_entity = effect_list.effect_entities[0]
    effect = world.component_for_entity(effect_entity, Effect)
    assert effect.count == 2

    health = world.component_for_entity(human, Health)
    assert health.current == health.max_hp - 5


def test_bleeding_falls_back_to_afflicted_owner_when_no_source():
    bus = EventBus()
    world = create_world(bus)
    EffectLifecycleSystem(world, bus)
    BleedingEffectSystem(world, bus)
    HealthSystem(world, bus)

    enemy = _find_enemy(world)

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=enemy,
        slug="bleeding",
        metadata={"count": 4},
    )

    captured = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda sender, **payload: captured.append(payload))

    _emit_bank_gain(bus, enemy, amount=3)

    assert captured, "Bleeding should still trigger when owner has no source reference"
    payload = captured[-1]
    assert payload["target_entity"] == enemy
    assert payload["amount"] == 3

    health = world.component_for_entity(enemy, Health)
    assert health.current == health.max_hp - 3

    effect_list = world.component_for_entity(enemy, EffectList)
    effect_entity = effect_list.effect_entities[0]
    effect = world.component_for_entity(effect_entity, Effect)
    assert effect.count == 1


def test_bleeding_ignores_non_blood_gains():
    bus = EventBus()
    world = create_world(bus)
    EffectLifecycleSystem(world, bus)
    BleedingEffectSystem(world, bus)
    HealthSystem(world, bus)

    human = _find_human(world)
    enemy = _find_enemy(world)

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=human,
        slug="bleeding",
        metadata={"count": 4, "source_owner": enemy},
    )

    _emit_bank_gain(bus, enemy, type_name="chaos", amount=3)

    effect_list = world.component_for_entity(human, EffectList)
    effect_entity = effect_list.effect_entities[0]
    effect = world.component_for_entity(effect_entity, Effect)
    assert effect.count == 4

    health = world.component_for_entity(human, Health)
    assert health.current == health.max_hp


def test_bleeding_caps_damage_to_remaining_stacks():
    bus = EventBus()
    world = create_world(bus)
    EffectLifecycleSystem(world, bus)
    BleedingEffectSystem(world, bus)
    HealthSystem(world, bus)

    human = _find_human(world)
    enemy = _find_enemy(world)

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=human,
        slug="bleeding",
        metadata={"count": 3, "source_owner": enemy},
    )

    captured = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda sender, **payload: captured.append(payload))

    _emit_bank_gain(bus, enemy, amount=5)

    assert captured, "Bleeding should deal damage when stacks remain"
    payload = captured[-1]
    assert payload["target_entity"] == human
    assert payload["amount"] == 3

    effect_list = world.component_for_entity(human, EffectList)
    assert not effect_list.effect_entities

    health = world.component_for_entity(human, Health)
    assert health.current == health.max_hp - 3


def test_bleeding_triggers_when_blood_tiles_are_matched():
    bus = EventBus()
    world = create_world(bus)
    TileBankSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    BleedingEffectSystem(world, bus)
    HealthSystem(world, bus)

    human = _find_human(world)
    enemy = _find_enemy(world)

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=human,
        slug="bleeding",
        metadata={"count": 4, "source_owner": enemy},
    )

    captured = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda sender, **payload: captured.append(payload))

    bus.emit(
        EVENT_TILES_MATCHED,
        owner_entity=enemy,
        types=[(0, 0, "blood"), (0, 1, "nature"), (0, 2, "blood")],
        positions=[(0, 0), (0, 1), (0, 2)],
        source="test",
    )

    assert captured, "Bleeding should trigger when blood tiles are matched"
    payload = captured[-1]
    assert payload["target_entity"] == human
    assert payload["amount"] == 2

    effect_list = world.component_for_entity(human, EffectList)
    effect_entity = effect_list.effect_entities[0]
    effect = world.component_for_entity(effect_entity, Effect)
    assert effect.count == 2
