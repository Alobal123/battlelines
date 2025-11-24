from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_EXECUTE,
    EVENT_EFFECT_APPLY,
    EVENT_HEALTH_DAMAGE,
)
from world import create_world
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.effect import Effect
from ecs.components.effect_duration import EffectDuration
from ecs.components.effect_list import EffectList
from ecs.components.health import Health
from ecs.components.human_agent import HumanAgent
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.factories.abilities import create_ability_by_name
from ecs.systems.ability_resolution_system import AbilityResolutionSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.damage_effect_system import DamageEffectSystem
from ecs.systems.effects.thorns_effect_system import ThornsEffectSystem
from ecs.systems.health_system import HealthSystem


def _setup_world():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    HealthSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    DamageEffectSystem(world, bus)
    AbilityResolutionSystem(world, bus)
    ThornsEffectSystem(world, bus)
    return bus, world


def _human_entity(world):
    return next(ent for ent, _ in world.get_component(HumanAgent))


def _enemy_entity(world):
    return next(ent for ent, _ in world.get_component(RuleBasedAgent))


def _activate_self_ability(bus, ability_entity, owner_entity):
    pending = PendingAbilityTarget(
        ability_entity=ability_entity,
        owner_entity=owner_entity,
        row=None,
        col=None,
        target_entity=owner_entity,
    )
    bus.emit(
        EVENT_ABILITY_EXECUTE,
        ability_entity=ability_entity,
        owner_entity=owner_entity,
        pending=pending,
    )


def _ensure_thorned_ward(bus, world, owner_entity):
    owner_comp: AbilityListOwner = world.component_for_entity(owner_entity, AbilityListOwner)
    thorned_ward = create_ability_by_name(world, "thorned_ward")
    owner_comp.ability_entities.append(thorned_ward)
    _activate_self_ability(bus, thorned_ward, owner_entity)
    return thorned_ward


def test_thorned_ward_applies_thorns_effect():
    bus, world = _setup_world()
    human = _human_entity(world)
    _ensure_thorned_ward(bus, world, human)

    effect_list: EffectList = world.component_for_entity(human, EffectList)
    thorns_effects = [
        effect_id
        for effect_id in effect_list.effect_entities
        if world.component_for_entity(effect_id, Effect).slug == "thorns"
    ]
    assert thorns_effects, "Thorned Ward should apply a thorns effect"
    effect_entity = thorns_effects[0]
    duration: EffectDuration = world.component_for_entity(effect_entity, EffectDuration)
    assert duration.remaining_turns == 3


def test_thorned_ward_reflects_ability_damage():
    bus, world = _setup_world()
    human = _human_entity(world)
    enemy = _enemy_entity(world)

    _ensure_thorned_ward(bus, world, human)

    enemy_owner: AbilityListOwner = world.component_for_entity(enemy, AbilityListOwner)
    blood_bolt = create_ability_by_name(world, "blood_bolt")
    enemy_owner.ability_entities.append(blood_bolt)

    damage_events = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda sender, **payload: damage_events.append(payload))

    human_health: Health = world.component_for_entity(human, Health)
    enemy_health: Health = world.component_for_entity(enemy, Health)
    human_initial = human_health.current
    enemy_initial = enemy_health.current

    _activate_self_ability(bus, blood_bolt, enemy)

    # Opponent should take the advertised damage from Blood Bolt (5)
    assert human_health.current == human_initial - 5
    # Attacker should take self-damage (2) plus reflected thorns (2)
    assert enemy_health.current == enemy_initial - 4

    thorns_hits = [event for event in damage_events if event.get("reason") == "thorns"]
    assert len(thorns_hits) == 1, "Exactly one thorns retaliation expected"
    assert thorns_hits[0]["target_entity"] == enemy
    assert thorns_hits[0]["amount"] == 2

    # Ensure self-damage did not produce an additional retaliation
    self_hits = [event for event in damage_events if event.get("reason") == "blood_bolt_self"]
    assert len(self_hits) == 1


def test_thorned_ward_reflects_witchfire_only():
    bus, world = _setup_world()
    human = _human_entity(world)
    enemy = _enemy_entity(world)

    _ensure_thorned_ward(bus, world, human)

    damage_events = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda sender, **payload: damage_events.append(payload))

    human_health: Health = world.component_for_entity(human, Health)
    enemy_health: Health = world.component_for_entity(enemy, Health)
    human_initial = human_health.current
    enemy_initial = enemy_health.current

    # Witchfire damage should trigger thorns retaliation
    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=human,
        source_entity=None,
        slug="damage",
        turns=0,
        metadata={
            "amount": 3,
            "reason": "witchfire",
            "source_owner": enemy,
        },
    )

    assert human_health.current == human_initial - 3
    assert enemy_health.current == enemy_initial - 2

    witchfire_retaliations = [event for event in damage_events if event.get("reason") == "thorns"]
    assert len(witchfire_retaliations) == 1

    # Chaos backlash should not trigger thorns
    damage_events.clear()
    enemy_after_witchfire = enemy_health.current

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=human,
        source_entity=None,
        slug="damage",
        turns=0,
        metadata={
            "amount": 4,
            "reason": "chaos",
            "source_owner": enemy,
        },
    )

    assert human_health.current == human_initial - 7
    assert enemy_health.current == enemy_after_witchfire
    assert not any(event.get("reason") == "thorns" for event in damage_events)
