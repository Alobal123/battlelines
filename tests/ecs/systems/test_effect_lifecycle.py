import pytest
from esper import World

from ecs.events.bus import (
    EventBus,
    EVENT_EFFECT_APPLY,
    EVENT_EFFECT_EXPIRED,
    EVENT_EFFECT_REFRESHED,
    EVENT_BATTLE_RESOLVED,
)
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.components.effect_list import EffectList
from ecs.components.effect import Effect
from ecs.components.effect_duration import EffectDuration
from ecs.effects.registry import EffectDefinition, default_effect_registry, register_effect
from ecs.events.bus import EVENT_TURN_ADVANCED


@pytest.fixture
def lifecycle_world():
    bus = EventBus()
    world = World()
    if not default_effect_registry.has("test_buff"):
        register_effect(
            EffectDefinition(
                slug="test_buff",
                display_name="Test Buff",
                description="A stackable test effect.",
                default_metadata={"value": 1},
            )
        )
    system = EffectLifecycleSystem(world, bus)
    owner = world.create_entity()
    return bus, world, system, owner


def _effect_entities(world: World, owner: int) -> list[int]:
    effect_list = world.component_for_entity(owner, EffectList)
    return list(effect_list.effect_entities)


def test_effects_stack_when_allowed(lifecycle_world):
    bus, world, _system, owner = lifecycle_world
    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=owner,
        slug="test_buff",
        stacks=True,
        metadata={"value": 1},
    )
    first_entities = _effect_entities(world, owner)
    assert len(first_entities) == 1
    first_effect = first_entities[0]
    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=owner,
        slug="test_buff",
        stacks=True,
        metadata={"value": 3},
    )
    second_entities = _effect_entities(world, owner)
    assert len(second_entities) == 2
    assert first_effect in second_entities
    # Ensure second instance has independent metadata
    second_effect = [ent for ent in second_entities if ent != first_effect][0]
    second_comp = world.component_for_entity(second_effect, Effect)
    assert second_comp.metadata["value"] == 3


def test_refresh_updates_metadata_and_duration(lifecycle_world):
    bus, world, _system, owner = lifecycle_world
    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=owner,
        slug="shield",
        metadata={"bonus": 5},
        turns=10,
    )
    effect_entity = _effect_entities(world, owner)[0]
    original_duration = world.component_for_entity(effect_entity, EffectDuration)
    assert original_duration.remaining_turns == 10
    refresh_payload: dict = {}

    def _record_refresh(sender, **payload):
        refresh_payload.update(payload)

    bus.subscribe(EVENT_EFFECT_REFRESHED, _record_refresh)
    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=owner,
        slug="shield",
        metadata={"bonus": 9},
        turns=4,
        refresh=True,
    )
    refreshed_entities = _effect_entities(world, owner)
    assert refreshed_entities == [effect_entity], "Refresh should not create a new effect"
    effect_comp = world.component_for_entity(effect_entity, Effect)
    assert effect_comp.metadata["bonus"] == 9
    refreshed_duration = world.component_for_entity(effect_entity, EffectDuration)
    assert refreshed_duration.remaining_turns == 4
    assert refresh_payload.get("effect_entity") == effect_entity


def test_effect_expires_on_event_payload_match(lifecycle_world):
    bus, world, _system, owner = lifecycle_world
    expired_events: list[dict] = []

    def _record_expired(sender, **payload):
        expired_events.append(payload)

    bus.subscribe(EVENT_EFFECT_EXPIRED, _record_expired)
    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=owner,
        slug="battle_focus",
        metadata={},
        expire_on_events=(EVENT_BATTLE_RESOLVED,),
        expire_match_owner=True,
        expire_payload_owner_key="attacker_owner",
    )
    effect_entity = _effect_entities(world, owner)[0]
    # Emit event with mismatched owner; effect should remain
    bus.emit(
        EVENT_BATTLE_RESOLVED,
        attacker_owner=-1,
        defender_owner=owner,
        forward={},
        counter={},
    )
    assert effect_entity in _effect_entities(world, owner)
    # Emit event with matching owner; effect should expire
    bus.emit(
        EVENT_BATTLE_RESOLVED,
        attacker_owner=owner,
        defender_owner=-1,
        forward={},
        counter={},
    )
    assert effect_entity not in _effect_entities(world, owner)
    assert expired_events, "Expected expiry event to fire"
    last_expired = expired_events[-1]
    assert last_expired.get("effect_entity") == effect_entity
    assert last_expired.get("reason") == f"event:{EVENT_BATTLE_RESOLVED}"


def test_turn_advanced_ticks_duration_and_expires(lifecycle_world):
    bus, world, _system, owner = lifecycle_world
    expired_payloads: list[dict] = []

    def _record_expired(sender, **payload):
        expired_payloads.append(payload)

    bus.subscribe(EVENT_EFFECT_EXPIRED, _record_expired)
    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=owner,
        slug="test_buff",
        metadata={"value": 10},
        turns=3,
    )
    effect_entities = _effect_entities(world, owner)
    assert len(effect_entities) == 1
    effect_entity = effect_entities[0]
    duration_comp = world.component_for_entity(effect_entity, EffectDuration)
    assert duration_comp.remaining_turns == 3
    # Advance unrelated owner id -> no tick
    bus.emit(EVENT_TURN_ADVANCED, previous_owner=999, new_owner=owner)
    assert world.component_for_entity(effect_entity, EffectDuration).remaining_turns == 3
    # Advance matching owner id -> ticks
    for expected in (2, 1, 0):
        bus.emit(EVENT_TURN_ADVANCED, previous_owner=owner, new_owner=None)
        if expected > 0:
            assert world.component_for_entity(effect_entity, EffectDuration).remaining_turns == expected
    assert not _effect_entities(world, owner)
    assert expired_payloads[-1]["effect_entity"] == effect_entity
