from __future__ import annotations

import random

from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_EFFECT_APPLIED,
    EVENT_ABILITY_EXECUTE,
    EVENT_CASCADE_COMPLETE,
    EVENT_HEALTH_HEAL,
)
from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.effect import Effect
from ecs.components.health import Health
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.factories.abilities import create_ability_by_name
from ecs.systems.ability_resolution_system import AbilityResolutionSystem
from ecs.systems.board import BoardSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.heal_effect_system import HealEffectSystem
from ecs.systems.health_system import HealthSystem
from ecs.systems.turn_state_utils import get_or_create_turn_state
from world import create_world


def _seed_rng(world, seed: int = 1) -> None:
    rng = getattr(world, "random", None)
    if isinstance(rng, random.Random):
        rng.seed(seed)


def test_mighty_bark_definition():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)

    ability_entity = create_ability_by_name(world, "mighty_bark")
    ability = world.component_for_entity(ability_entity, Ability)
    assert ability.cost == {"shapeshift": 4}
    assert ability.ends_turn is True
    assert ability.params.get("heal_per_tile") == 2


def test_mighty_bark_heals_per_guarded_tile():
    bus = EventBus()
    world = create_world(bus)

    EffectLifecycleSystem(world, bus)
    HealEffectSystem(world, bus)
    HealthSystem(world, bus)
    AbilityResolutionSystem(world, bus)

    board = BoardSystem(world, bus, rows=1, cols=5)
    for col in range(5):
        entity = board._get_entity_at(0, col)
        assert entity is not None

    _seed_rng(world, seed=1)

    enemy_pool = getattr(world, "enemy_pool")
    mastiffs = enemy_pool.create_enemy("mastiffs")

    owner = world.component_for_entity(mastiffs, AbilityListOwner)
    guard_entity = next(
        ent for ent in owner.ability_entities if world.component_for_entity(ent, Ability).name == "guard"
    )
    pending_guard = PendingAbilityTarget(
        ability_entity=guard_entity,
        owner_entity=mastiffs,
        row=None,
        col=None,
        target_entity=mastiffs,
    )
    bus.emit(
        EVENT_ABILITY_EXECUTE,
        ability_entity=guard_entity,
        owner_entity=mastiffs,
        pending=pending_guard,
    )

    guarded_tiles = [
        effect
        for _, effect in world.get_component(Effect)
        if effect.slug == "tile_guarded" and effect.metadata.get("source_owner") == mastiffs
    ]
    assert len(guarded_tiles) == 5, "Guard ability should guard five tiles on a 1x5 board"

    mighty_entity = next(
        ent
        for ent in owner.ability_entities
        if world.component_for_entity(ent, Ability).name == "mighty_bark"
    )
    health = world.component_for_entity(mastiffs, Health)
    health.current = max(0, health.current - 12)
    before_health = health.current

    heal_events: list[dict] = []
    ability_events: list[dict] = []
    bus.subscribe(EVENT_HEALTH_HEAL, lambda sender, **payload: heal_events.append(payload))
    bus.subscribe(EVENT_ABILITY_EFFECT_APPLIED, lambda sender, **payload: ability_events.append(payload))

    pending = PendingAbilityTarget(
        ability_entity=mighty_entity,
        owner_entity=mastiffs,
        row=None,
        col=None,
        target_entity=mastiffs,
    )
    bus.emit(
        EVENT_ABILITY_EXECUTE,
        ability_entity=mighty_entity,
        owner_entity=mastiffs,
        pending=pending,
    )

    assert heal_events, "Mighty Bark should emit a heal event"
    heal_payload = heal_events[-1]
    expected_amount = len(guarded_tiles) * 2
    assert heal_payload["amount"] == expected_amount
    assert heal_payload.get("reason") == "mighty_bark"
    assert heal_payload["target_entity"] == mastiffs

    capped = min(world.component_for_entity(mastiffs, Health).max_hp, before_health + expected_amount)
    assert world.component_for_entity(mastiffs, Health).current == capped

    assert ability_events, "Ability effect applied event should fire"
    asserted = ability_events[-1]
    assert asserted.get("ability_entity") == mighty_entity
    assert asserted.get("affected") == [mastiffs]


def test_mighty_bark_without_guarded_tiles_still_completes_turn():
    bus = EventBus()
    world = create_world(bus)

    EffectLifecycleSystem(world, bus)
    HealEffectSystem(world, bus)
    HealthSystem(world, bus)
    AbilityResolutionSystem(world, bus)

    enemy_pool = getattr(world, "enemy_pool")
    mastiffs = enemy_pool.create_enemy("mastiffs")

    owner = world.component_for_entity(mastiffs, AbilityListOwner)
    mighty_entity = next(
        ent
        for ent in owner.ability_entities
        if world.component_for_entity(ent, Ability).name == "mighty_bark"
    )

    heal_events: list[dict] = []
    ability_events: list[dict] = []
    cascade_events: list[dict] = []
    bus.subscribe(EVENT_HEALTH_HEAL, lambda sender, **payload: heal_events.append(payload))
    bus.subscribe(EVENT_ABILITY_EFFECT_APPLIED, lambda sender, **payload: ability_events.append(payload))
    bus.subscribe(EVENT_CASCADE_COMPLETE, lambda sender, **payload: cascade_events.append(payload))

    pending = PendingAbilityTarget(
        ability_entity=mighty_entity,
        owner_entity=mastiffs,
        row=None,
        col=None,
        target_entity=mastiffs,
    )
    bus.emit(
        EVENT_ABILITY_EXECUTE,
        ability_entity=mighty_entity,
        owner_entity=mastiffs,
        pending=pending,
    )

    assert not heal_events, "No guarded tiles should prevent healing"
    assert ability_events, "Ability effect event should be emitted"
    assert ability_events[-1].get("affected") == []
    assert cascade_events, "Cascade completion should still be emitted"
    state = get_or_create_turn_state(world)
    assert state.cascade_observed is False
