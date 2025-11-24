from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_EXECUTE,
    EVENT_HEALTH_DAMAGE,
    EVENT_HEALTH_HEAL,
)
from world import create_world
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.ability import Ability
from ecs.components.ability_effect import AbilityEffects
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.health import Health
from ecs.factories.abilities import create_ability_by_name
from ecs.systems.health_system import HealthSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.damage_effect_system import DamageEffectSystem
from ecs.systems.effects.heal_effect_system import HealEffectSystem
from ecs.systems.ability_resolution_system import AbilityResolutionSystem


def _setup_world():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    HealthSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    DamageEffectSystem(world, bus)
    HealEffectSystem(world, bus)
    AbilityResolutionSystem(world, bus)
    return bus, world


def _human_entity(world):
    return next(ent for ent, _ in world.get_component(HumanAgent))


def _enemy_entity(world):
    return next(ent for ent, _ in world.get_component(RuleBasedAgent))


def _life_drain_damage(world, ability_entity):
    ability = world.component_for_entity(ability_entity, Ability)
    amount = ability.params.get("damage_amount")
    if amount is not None:
        return int(amount)
    effects = world.component_for_entity(ability_entity, AbilityEffects)
    for spec in effects.effects:
        if spec.slug == "damage" and spec.metadata.get("amount") is not None:
            return int(spec.metadata["amount"])
    raise AssertionError("life_drain ability should declare a damage amount")


def test_life_drain_damages_enemy_and_heals_caster():
    bus, world = _setup_world()
    human = _human_entity(world)
    enemy = _enemy_entity(world)

    ability_owner: AbilityListOwner = world.component_for_entity(human, AbilityListOwner)
    life_drain = create_ability_by_name(world, "life_drain")
    ability_owner.ability_entities.append(life_drain)
    ability = world.component_for_entity(life_drain, Ability)

    assert ability.cost.get("blood") == 7
    assert all(count == 0 for name, count in ability.cost.items() if name != "blood")

    damage_amount = _life_drain_damage(world, life_drain)

    human_health: Health = world.component_for_entity(human, Health)
    enemy_health: Health = world.component_for_entity(enemy, Health)
    human_health.current = max(0, human_health.current - 5)
    enemy_initial = enemy_health.current
    human_initial = human_health.current

    damage_events: list[dict] = []
    heal_events: list[dict] = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda s, **k: damage_events.append(k))
    bus.subscribe(EVENT_HEALTH_HEAL, lambda s, **k: heal_events.append(k))

    pending = PendingAbilityTarget(
        ability_entity=life_drain,
        owner_entity=human,
        row=None,
        col=None,
        target_entity=human,
    )

    bus.emit(
        EVENT_ABILITY_EXECUTE,
        ability_entity=life_drain,
        owner_entity=human,
        pending=pending,
    )

    assert damage_events, "life_drain should emit a damage event"
    life_drain_damage = [event for event in damage_events if event.get("reason") == "life_drain"]
    assert len(life_drain_damage) == 1
    assert life_drain_damage[0]["target_entity"] == enemy
    assert life_drain_damage[0]["source_owner"] == human
    assert life_drain_damage[0]["amount"] == damage_amount

    actual_damage = enemy_initial - enemy_health.current
    assert actual_damage == damage_amount

    assert heal_events, "life_drain should emit a heal event"
    caster_heals = [event for event in heal_events if event.get("target_entity") == human]
    assert len(caster_heals) == 1
    assert caster_heals[0]["reason"] == "life_drain"

    actual_heal = human_health.current - human_initial
    assert actual_heal == damage_amount
    assert caster_heals[0]["amount"] == actual_heal


def test_life_drain_heal_matches_damage_dealt_after_clamp():
    bus, world = _setup_world()
    human = _human_entity(world)
    enemy = _enemy_entity(world)

    ability_owner: AbilityListOwner = world.component_for_entity(human, AbilityListOwner)
    life_drain = create_ability_by_name(world, "life_drain")
    ability_owner.ability_entities.append(life_drain)

    human_health: Health = world.component_for_entity(human, Health)
    enemy_health: Health = world.component_for_entity(enemy, Health)
    human_health.current = max(0, human_health.current - 10)
    human_initial = human_health.current
    enemy_health.current = 1
    enemy_initial = enemy_health.current

    damage_events: list[dict] = []
    heal_events: list[dict] = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda s, **k: damage_events.append(k))
    bus.subscribe(EVENT_HEALTH_HEAL, lambda s, **k: heal_events.append(k))

    pending = PendingAbilityTarget(
        ability_entity=life_drain,
        owner_entity=human,
        row=None,
        col=None,
        target_entity=human,
    )

    bus.emit(
        EVENT_ABILITY_EXECUTE,
        ability_entity=life_drain,
        owner_entity=human,
        pending=pending,
    )

    assert enemy_health.current == 0
    actual_damage = enemy_initial - enemy_health.current

    assert heal_events, "life_drain should emit a heal event when damage resolves"
    caster_heal = [event for event in heal_events if event.get("target_entity") == human]
    assert len(caster_heal) == 1
    assert caster_heal[0]["amount"] == actual_damage
    assert human_health.current - human_initial == actual_damage
