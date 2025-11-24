from __future__ import annotations

from typing import cast

from ecs.events.bus import EventBus, EVENT_ABILITY_EXECUTE, EVENT_EFFECT_APPLY, EVENT_HEALTH_DAMAGE
from world import create_world
from ecs.components.ability import Ability
from ecs.components.ability_effect import AbilityEffects
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.health import Health
from ecs.components.human_agent import HumanAgent
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.factories.abilities import create_ability_by_name
from ecs.systems.ability_resolution_system import AbilityResolutionSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.damage_effect_system import DamageEffectSystem
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


def test_go_for_throat_definition():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)

    ability_entity = create_ability_by_name(world, "go_for_throat")
    ability = world.component_for_entity(ability_entity, Ability)
    assert ability.cost == {"shapeshift": 7}
    assert ability.ends_turn is True

    effects = world.component_for_entity(ability_entity, AbilityEffects)
    assert effects.effects
    spec = effects.effects[0]
    assert spec.slug == "damage"
    assert spec.target == "opponent"
    assert spec.metadata.get("reason") == "go_for_throat"


def test_go_for_throat_scales_with_locked_scent():
    bus = EventBus()
    world = create_world(bus)

    HealthSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    DamageEffectSystem(world, bus)
    AbilityResolutionSystem(world, bus)

    human = _human(world)
    enemy = _enemy(world)

    ability_entity = create_ability_by_name(world, "go_for_throat")
    owner_comp = cast(AbilityListOwner, world.component_for_entity(enemy, AbilityListOwner))
    owner_comp.ability_entities = [ability_entity]

    damage_events: list[dict] = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda sender, **payload: damage_events.append(payload))

    def _execute() -> int:
        damage_events.clear()
        bus.emit(
            EVENT_ABILITY_EXECUTE,
            ability_entity=ability_entity,
            owner_entity=enemy,
            pending=_pending(ability_entity, enemy),
        )
        assert damage_events, "go_for_throat should always deal damage"
        return damage_events[-1]["amount"]

    base_damage = _execute()
    assert base_damage == 3

    for _ in range(2):
        bus.emit(
            EVENT_EFFECT_APPLY,
            owner_entity=human,
            slug="locked_scent",
            metadata={},
        )

    stacked_damage = _execute()
    assert stacked_damage == 3 + (2 * 2)

    human_health = world.component_for_entity(human, Health)
    assert human_health.current < human_health.max_hp
