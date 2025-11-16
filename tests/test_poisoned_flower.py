from ecs.events.bus import EventBus, EVENT_ABILITY_EXECUTE, EVENT_HEALTH_DAMAGE, EVENT_TURN_ADVANCED
from ecs.world import create_world
from ecs.components.ability import Ability
from ecs.components.ability_effect import AbilityEffects
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
from ecs.systems.effects.poison_effect_system import PoisonEffectSystem
from ecs.systems.health_system import HealthSystem


def _human(world):
    return next(ent for ent, _ in world.get_component(HumanAgent))


def _enemy(world):
    return next(ent for ent, _ in world.get_component(RuleBasedAgent))


def _pending(ability_entity: int, owner_entity: int) -> PendingAbilityTarget:
    return PendingAbilityTarget(
        ability_entity=ability_entity,
        owner_entity=owner_entity,
        row=None,
        col=None,
        target_entity=owner_entity,
    )


def test_poisoned_flower_definition():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)

    ability_entity = create_ability_by_name(world, "poisoned_flower")
    ability = world.component_for_entity(ability_entity, Ability)
    assert ability.cost == {"nature": 3, "hex": 1}

    effects = world.component_for_entity(ability_entity, AbilityEffects)
    assert len(effects.effects) == 1
    spec = effects.effects[0]
    assert spec.slug == "poison"
    assert spec.turns == 3
    assert spec.metadata["amount"] == 2
    assert spec.metadata.get("source_owner") is None


def test_poisoned_flower_applies_poison_and_ticks():
    bus = EventBus()
    world = create_world(bus)

    HealthSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    PoisonEffectSystem(world, bus)
    AbilityResolutionSystem(world, bus)

    human = _human(world)
    enemy = _enemy(world)

    owner_comp: AbilityListOwner = world.component_for_entity(enemy, AbilityListOwner)
    ability_entity = create_ability_by_name(world, "poisoned_flower")
    owner_comp.ability_entities.append(ability_entity)

    health_before = world.component_for_entity(human, Health).current

    damage_events = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda sender, **payload: damage_events.append(payload))

    bus.emit(
        EVENT_ABILITY_EXECUTE,
        ability_entity=ability_entity,
        owner_entity=enemy,
        pending=_pending(ability_entity, enemy),
    )

    effect_list: EffectList = world.component_for_entity(human, EffectList)
    assert effect_list.effect_entities, "Poisoned Flower should apply a poison effect"
    effect_entity = effect_list.effect_entities[0]
    effect = world.component_for_entity(effect_entity, Effect)
    assert effect.slug == "poison"
    assert effect.metadata.get("amount") == 2
    assert effect.metadata.get("reason") == "poison"
    assert effect.metadata.get("source_owner") is None
    duration = world.component_for_entity(effect_entity, EffectDuration)
    assert duration.remaining_turns == 3

    bus.emit(EVENT_TURN_ADVANCED, previous_owner=None, new_owner=human)

    assert damage_events, "Poison should have dealt damage at start of afflicted turn"
    payload = damage_events[-1]
    assert payload["target_entity"] == human
    assert payload["amount"] == 2
    assert payload.get("reason") == "poison"
    assert payload.get("source_owner") is None

    health_after = world.component_for_entity(human, Health).current
    assert health_after == health_before - 2
