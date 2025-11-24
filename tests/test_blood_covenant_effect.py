from esper import World

from ecs.events.bus import EventBus, EVENT_EFFECT_APPLY, EVENT_HEALTH_DAMAGE, EVENT_TURN_ADVANCED
from world import create_world
from ecs.components.health import Health
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.damage_effect_system import DamageEffectSystem
from ecs.systems.effects.blood_covenant_effect_system import BloodCovenantEffectSystem
from ecs.systems.health_system import HealthSystem


def _setup_systems(world: World, bus: EventBus) -> None:
    HealthSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    DamageEffectSystem(world, bus)
    BloodCovenantEffectSystem(world, bus)


def _players(world: World) -> tuple[int, int]:
    owner = next(entity for entity, _ in world.get_component(HumanAgent))
    opponent = next(entity for entity, _ in world.get_component(RuleBasedAgent))
    return owner, opponent


def test_blood_covenant_damages_owner_and_opponent() -> None:
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    _setup_systems(world, bus)

    owner, opponent = _players(world)

    owner_health: Health = world.component_for_entity(owner, Health)
    opponent_health: Health = world.component_for_entity(opponent, Health)
    starting_owner = owner_health.current
    starting_opponent = opponent_health.current

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=owner,
        source_entity=None,
        slug="blood_covenant",
        turns=None,
    )

    damage_events: list[dict] = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda s, **k: damage_events.append(k))

    bus.emit(EVENT_TURN_ADVANCED, previous_owner=None, new_owner=owner)

    assert len(damage_events) == 2
    targets = {event.get("target_entity") for event in damage_events}
    assert targets == {owner, opponent}

    for event in damage_events:
        assert event.get("amount") == 1
        assert event.get("reason") == "blood_covenant"
        assert event.get("source_owner") == owner

    assert owner_health.current == starting_owner - 1
    assert opponent_health.current == starting_opponent - 1


def test_blood_covenant_uses_metadata_amount() -> None:
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    _setup_systems(world, bus)

    owner, opponent = _players(world)

    owner_health: Health = world.component_for_entity(owner, Health)
    opponent_health: Health = world.component_for_entity(opponent, Health)
    starting_owner = owner_health.current
    starting_opponent = opponent_health.current

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=owner,
        source_entity=None,
        slug="blood_covenant",
        turns=None,
        metadata={"amount": 3},
    )

    bus.emit(EVENT_TURN_ADVANCED, previous_owner=None, new_owner=owner)

    assert owner_health.current == starting_owner - 3
    assert opponent_health.current == starting_opponent - 3
