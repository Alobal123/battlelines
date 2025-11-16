from ecs.events.bus import EventBus, EVENT_ABILITY_EXECUTE, EVENT_EFFECT_APPLY
from ecs.world import create_world
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.effect_list import EffectList
from ecs.components.effect import Effect
from ecs.components.effect_duration import EffectDuration
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


def test_curse_of_frailty_applies_and_stacks():
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

    effect_list: EffectList = world.component_for_entity(enemy_ent, EffectList)
    assert len(effect_list.effect_entities) == 1
    effect_entity = effect_list.effect_entities[0]
    effect = world.component_for_entity(effect_entity, Effect)
    assert effect.slug == "frailty"
    duration = world.component_for_entity(effect_entity, EffectDuration)
    assert duration.remaining_turns == 3

    enemy_health: Health = world.component_for_entity(enemy_ent, Health)
    initial_hp = enemy_health.current

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=enemy_ent,
        slug="damage",
        metadata={"amount": 2, "source_owner": human_ent},
        turns=0,
    )

    assert enemy_health.current == initial_hp - 3

    # Apply a second stack and ensure it amplifies further damage.
    bus.emit(
        EVENT_ABILITY_EXECUTE,
        ability_entity=frailty_ability,
        owner_entity=human_ent,
        pending=_pending(frailty_ability, human_ent),
    )

    effect_list = world.component_for_entity(enemy_ent, EffectList)
    assert len(effect_list.effect_entities) == 2

    mid_hp = enemy_health.current
    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=enemy_ent,
        slug="damage",
        metadata={"amount": 2, "source_owner": human_ent},
        turns=0,
    )

    assert enemy_health.current == mid_hp - 4
