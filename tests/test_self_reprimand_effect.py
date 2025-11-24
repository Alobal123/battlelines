from esper import World

from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_EXECUTE,
    EVENT_EFFECT_REMOVE,
    EVENT_HEALTH_DAMAGE,
    EVENT_TILE_BANK_GAINED,
)
from world import create_world
from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.health import Health
from ecs.components.human_agent import HumanAgent
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.tile_bank import TileBank
from ecs.systems.ability_resolution_system import AbilityResolutionSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.damage_effect_system import DamageEffectSystem
from ecs.systems.effects.self_reprimand_effect_system import SelfReprimandEffectSystem
from ecs.systems.health_system import HealthSystem
from ecs.systems.tile_bank_system import TileBankSystem
from ecs.systems.skills.apply_skill_effects_system import ApplySkillEffectsSystem

from tests.helpers import grant_player_abilities, grant_player_skills


def _setup_core_systems(world: World, bus: EventBus) -> None:
    HealthSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    ApplySkillEffectsSystem(world, bus)
    DamageEffectSystem(world, bus)
    TileBankSystem(world, bus)
    SelfReprimandEffectSystem(world, bus)
    AbilityResolutionSystem(world, bus)


def _prepare_player(world: World) -> None:
    grant_player_abilities(world, ("blood_bolt",))
    grant_player_skills(world, ("self_reprimand",))


def _players(world: World) -> tuple[int, int]:
    human = next(entity for entity, _ in world.get_component(HumanAgent))
    opponent = next(entity for entity, _ in world.get_component(RuleBasedAgent))
    return human, opponent


def _blood_bolt(world: World, owner: int) -> int:
    ability_owner: AbilityListOwner = world.component_for_entity(owner, AbilityListOwner)
    for ability_entity in ability_owner.ability_entities:
        ability = world.component_for_entity(ability_entity, Ability)
        if ability.name == "blood_bolt":
            return ability_entity
    raise AssertionError("blood_bolt ability not found")


def _tile_bank(world: World, owner: int) -> TileBank:
    for entity, bank in world.get_component(TileBank):
        if bank.owner_entity == owner:
            return bank
    raise AssertionError("tile bank not found")


def _activate_blood_bolt(bus: EventBus, ability_entity: int, owner: int) -> None:
    pending = PendingAbilityTarget(
        ability_entity=ability_entity,
        owner_entity=owner,
        row=None,
        col=None,
        target_entity=owner,
    )
    bus.emit(
        EVENT_ABILITY_EXECUTE,
        ability_entity=ability_entity,
        owner_entity=owner,
        pending=pending,
    )


def test_self_reprimand_triggers_extra_damage_and_blood_gain() -> None:
    bus = EventBus()
    world = create_world(bus)
    _prepare_player(world)
    _setup_core_systems(world, bus)

    owner, opponent = _players(world)
    ability_entity = _blood_bolt(world, owner)

    damage_events: list[dict] = []
    bank_events: list[dict] = []

    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda s, **k: damage_events.append(k))
    bus.subscribe(EVENT_TILE_BANK_GAINED, lambda s, **k: bank_events.append(k))

    enemy_health: Health = world.component_for_entity(opponent, Health)
    starting_enemy = enemy_health.current
    bank = _tile_bank(world, owner)
    starting_blood = bank.counts.get("blood", 0)

    _activate_blood_bolt(bus, ability_entity, owner)

    reasons = [event.get("reason") for event in damage_events]
    assert reasons.count("blood_bolt_self") == 1
    assert reasons.count("blood_bolt") == 1
    assert reasons.count("self_reprimand") == 1

    retaliation = next(event for event in damage_events if event.get("reason") == "self_reprimand")
    assert retaliation.get("target_entity") == opponent
    assert retaliation.get("amount") == 1
    assert retaliation.get("source_owner") == owner

    assert enemy_health.current == starting_enemy - 6

    assert any(
        event.get("owner_entity") == owner and event.get("type_name") == "blood" and event.get("amount") == 1
        for event in bank_events
    )
    assert bank.counts.get("blood", 0) == starting_blood + 1


def test_self_reprimand_absent_does_not_trigger() -> None:
    bus = EventBus()
    world = create_world(bus)
    _prepare_player(world)
    _setup_core_systems(world, bus)

    owner, opponent = _players(world)
    ability_entity = _blood_bolt(world, owner)

    damage_events: list[dict] = []
    bank_events: list[dict] = []

    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda s, **k: damage_events.append(k))
    bus.subscribe(EVENT_TILE_BANK_GAINED, lambda s, **k: bank_events.append(k))

    _activate_blood_bolt(bus, ability_entity, owner)

    bus.emit(
        EVENT_EFFECT_REMOVE,
        owner_entity=owner,
        slug="self_reprimand",
        remove_all=True,
    )

    damage_events.clear()
    bank_events.clear()

    _activate_blood_bolt(bus, ability_entity, owner)

    reasons = [event.get("reason") for event in damage_events]
    assert reasons.count("blood_bolt_self") == 1
    assert reasons.count("blood_bolt") == 1
    assert "self_reprimand" not in reasons
    assert not bank_events
