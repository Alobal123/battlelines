from ecs.events.bus import EventBus, EVENT_ABILITY_EXECUTE, EVENT_EFFECT_APPLY
from world import create_world
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.effect_list import EffectList
from ecs.components.effect import Effect
from ecs.components.effect_duration import EffectDuration
from ecs.components.ability_effect import AbilityEffects
from ecs.components.health import Health
from ecs.components.human_agent import HumanAgent
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.factories.abilities import create_ability_by_name
from ecs.systems.ability_resolution_system import AbilityResolutionSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.damage_effect_system import DamageEffectSystem
from ecs.systems.health_system import HealthSystem


def _human_entity(world):
    return next(ent for ent, _ in world.get_component(HumanAgent))


def _enemy_entity(world):
    return next(ent for ent, _ in world.get_component(RuleBasedAgent))


def _pending(ability_entity: int, owner_entity: int) -> PendingAbilityTarget:
    return PendingAbilityTarget(
        ability_entity=ability_entity,
        owner_entity=owner_entity,
        row=None,
        col=None,
        target_entity=None,
    )


def _frailty_effects(world, owner_entity: int) -> list[int]:
    try:
        effect_list: EffectList = world.component_for_entity(owner_entity, EffectList)
    except KeyError:
        return []
    result: list[int] = []
    for effect_entity in list(effect_list.effect_entities):
        try:
            effect = world.component_for_entity(effect_entity, Effect)
        except KeyError:
            continue
        if effect.slug == "frailty":
            result.append(effect_entity)
    return result


def _total_frailty_bonus(world, owner_entity: int) -> int:
    total = 0
    for effect_entity in _frailty_effects(world, owner_entity):
        try:
            effect = world.component_for_entity(effect_entity, Effect)
        except KeyError:
            continue
        try:
            total += int(effect.metadata.get("bonus", 0))
        except (TypeError, ValueError):
            continue
    return total


def test_curse_of_frailty_applies_and_accumulates():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)

    HealthSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    DamageEffectSystem(world, bus)
    AbilityResolutionSystem(world, bus)

    human_ent = _human_entity(world)
    enemy_ent = _enemy_entity(world)

    owner_comp: AbilityListOwner = world.component_for_entity(human_ent, AbilityListOwner)
    frailty_ability = create_ability_by_name(world, "curse_of_frailty")
    owner_comp.ability_entities.append(frailty_ability)

    bus.emit(
        EVENT_ABILITY_EXECUTE,
        ability_entity=frailty_ability,
        owner_entity=human_ent,
        pending=_pending(frailty_ability, human_ent),
    )

    effect_ids = _frailty_effects(world, enemy_ent)
    assert effect_ids, "Curse of Frailty should apply at least one frailty effect"
    effect_entity = effect_ids[0]
    effect = world.component_for_entity(effect_entity, Effect)
    duration = world.component_for_entity(effect_entity, EffectDuration)
    spec = world.component_for_entity(frailty_ability, AbilityEffects).effects[0]
    if spec.turns is not None:
        assert duration.remaining_turns == spec.turns
    else:
        assert duration.remaining_turns > 0

    enemy_health: Health = world.component_for_entity(enemy_ent, Health)
    initial_hp = enemy_health.current
    base_attack_amount = 2
    bonus_after_first = _total_frailty_bonus(world, enemy_ent)

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=enemy_ent,
        slug="damage",
        metadata={"amount": base_attack_amount, "source_owner": human_ent},
        turns=0,
    )

    assert enemy_health.current == initial_hp - (base_attack_amount + bonus_after_first)

    # Apply a second stack and ensure it amplifies further damage.
    bus.emit(
        EVENT_ABILITY_EXECUTE,
        ability_entity=frailty_ability,
        owner_entity=human_ent,
        pending=_pending(frailty_ability, human_ent),
    )

    bonus_after_second = _total_frailty_bonus(world, enemy_ent)
    assert bonus_after_second >= bonus_after_first

    mid_hp = enemy_health.current
    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=enemy_ent,
        slug="damage",
        metadata={"amount": base_attack_amount, "source_owner": human_ent},
        turns=0,
    )

    assert enemy_health.current == mid_hp - (base_attack_amount + bonus_after_second)
