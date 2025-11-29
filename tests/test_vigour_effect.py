from ecs.events.bus import EventBus, EVENT_HEALTH_HEAL
from ecs.components.health import Health
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.damage_effect_system import DamageEffectSystem
from ecs.systems.effects.vigour_effect_system import VigourEffectSystem
from ecs.systems.health_system import HealthSystem
from ecs.systems.skills.apply_skill_effects_system import ApplySkillEffectsSystem
from world import create_world

from tests.helpers import grant_player_skills


def _setup_core_systems(world, bus) -> None:
    HealthSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    ApplySkillEffectsSystem(world, bus)
    DamageEffectSystem(world, bus)
    VigourEffectSystem(world, bus)


def _players(world):
    owner = next(entity for entity, _ in world.get_component(HumanAgent))
    opponent = next(entity for entity, _ in world.get_component(RuleBasedAgent))
    return owner, opponent


def test_vigour_transforms_overheal_into_damage():
    bus = EventBus()
    world = create_world(bus)
    grant_player_skills(world, ("vigour",))
    _setup_core_systems(world, bus)

    owner, opponent = _players(world)
    owner_health: Health = world.component_for_entity(owner, Health)
    opponent_health: Health = world.component_for_entity(opponent, Health)

    owner_health.current = owner_health.max_hp - 1
    starting_enemy = opponent_health.current

    bus.emit(
        EVENT_HEALTH_HEAL,
        target_entity=owner,
        amount=5,
        source_owner=owner,
        reason="test_overheal",
    )

    assert opponent_health.current == starting_enemy - 4


def test_vigour_triggers_when_owner_is_full():
    bus = EventBus()
    world = create_world(bus)
    grant_player_skills(world, ("vigour",))
    _setup_core_systems(world, bus)

    owner, opponent = _players(world)
    owner_health: Health = world.component_for_entity(owner, Health)
    opponent_health: Health = world.component_for_entity(opponent, Health)

    owner_health.current = owner_health.max_hp
    starting_enemy = opponent_health.current

    bus.emit(
        EVENT_HEALTH_HEAL,
        target_entity=owner,
        amount=3,
        source_owner=owner,
        reason="test_full_overheal",
    )

    assert opponent_health.current == starting_enemy - 3
