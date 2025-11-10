import pytest

from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_ACTIVATE_REQUEST,
    EVENT_REGIMENT_CLICK,
    EVENT_TURN_ADVANCED,
)
from ecs.world import create_world
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.tile_bank_system import TileBankSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.army_roster import ArmyRoster
from ecs.components.regiment import Regiment
from ecs.components.tile_bank import TileBank
from ecs.components.effect_list import EffectList
from ecs.components.effect_duration import EffectDuration


def _find_ability(world, owner_entity, name: str) -> int:
    owner_comp = world.component_for_entity(owner_entity, AbilityListOwner)
    for ability_entity in owner_comp.ability_entities:
        ability = world.component_for_entity(ability_entity, Ability)
        if ability.name == name:
            return ability_entity
    raise AssertionError(f"Ability '{name}' not found for owner {owner_entity}")


def _get_tile_bank(world, owner_entity):
    for _, bank in world.get_component(TileBank):
        if bank.owner_entity == owner_entity:
            return bank
    raise AssertionError("Tile bank not found for owner")


def test_bolster_morale_applies_effect_and_expires():
    bus = EventBus()
    world = create_world(bus)
    AbilitySystem(world, bus)
    TileBankSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    owners = list(world.get_component(AbilityListOwner))
    assert len(owners) >= 2
    owner_entity = owners[0][0]
    other_owner = owners[1][0]
    roster: ArmyRoster = world.component_for_entity(owner_entity, ArmyRoster)
    target_regiment = roster.regiment_entities[0]
    regiment: Regiment = world.component_for_entity(target_regiment, Regiment)
    base_morale = regiment.morale
    bank = _get_tile_bank(world, owner_entity)
    starting_tactics = bank.counts.get("tactics", 0)
    ability_entity = _find_ability(world, owner_entity, "bolster_morale")

    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=ability_entity, owner_entity=owner_entity)
    # Ability should enter targeting state
    # Activate by clicking own regiment
    bus.emit(
        EVENT_REGIMENT_CLICK,
        owner_entity=owner_entity,
        regiment_entity=target_regiment,
    )

    # Effect should apply and morale should increase immediately
    regiment_after: Regiment = world.component_for_entity(target_regiment, Regiment)
    assert pytest.approx(regiment_after.morale) == base_morale + 20
    bank_after = _get_tile_bank(world, owner_entity)
    assert bank_after.counts["tactics"] == starting_tactics - 3
    effect_list: EffectList = world.component_for_entity(target_regiment, EffectList)
    assert len(effect_list.effect_entities) == 1
    effect_entity = effect_list.effect_entities[0]
    duration = world.component_for_entity(effect_entity, EffectDuration)
    assert duration.remaining_turns == 3

    # Advancing other owner's turn should not tick the buff
    bus.emit(EVENT_TURN_ADVANCED, previous_owner=other_owner, new_owner=owner_entity)
    duration = world.component_for_entity(effect_entity, EffectDuration)
    assert duration.remaining_turns == 3

    # Advance through three of the owner's turns to expire the effect
    for expected in (2, 1, 0):
        bus.emit(EVENT_TURN_ADVANCED, previous_owner=owner_entity, new_owner=other_owner)
        if expected > 0:
            duration = world.component_for_entity(effect_entity, EffectDuration)
            assert duration.remaining_turns == expected
        else:
            break

    effect_list = world.component_for_entity(target_regiment, EffectList)
    assert not effect_list.effect_entities
    final_regiment: Regiment = world.component_for_entity(target_regiment, Regiment)
    assert pytest.approx(final_regiment.morale) == base_morale


def test_bolster_morale_stacks_with_repeated_use():
    bus = EventBus()
    world = create_world(bus)
    AbilitySystem(world, bus)
    TileBankSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    owners = list(world.get_component(AbilityListOwner))
    owner_entity = owners[0][0]
    other_owner = owners[1][0]
    roster: ArmyRoster = world.component_for_entity(owner_entity, ArmyRoster)
    target_regiment = roster.regiment_entities[0]
    regiment: Regiment = world.component_for_entity(target_regiment, Regiment)
    base_morale = regiment.morale
    ability_entity = _find_ability(world, owner_entity, "bolster_morale")

    def _cast_once():
        bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=ability_entity, owner_entity=owner_entity)
        bus.emit(
            EVENT_REGIMENT_CLICK,
            owner_entity=owner_entity,
            regiment_entity=target_regiment,
        )

    _cast_once()
    regiment_after_first = world.component_for_entity(target_regiment, Regiment)
    assert pytest.approx(regiment_after_first.morale) == base_morale + 20

    _cast_once()
    regiment_after_second = world.component_for_entity(target_regiment, Regiment)
    assert pytest.approx(regiment_after_second.morale) == base_morale + 40

    effect_list: EffectList = world.component_for_entity(target_regiment, EffectList)
    assert len(effect_list.effect_entities) == 2
    durations = [world.component_for_entity(ent, EffectDuration).remaining_turns for ent in effect_list.effect_entities]
    assert durations == [3, 3]

    for expected in (2, 1, 0):
        bus.emit(EVENT_TURN_ADVANCED, previous_owner=owner_entity, new_owner=other_owner)
        if expected > 0:
            durations = [world.component_for_entity(ent, EffectDuration).remaining_turns for ent in effect_list.effect_entities]
            assert all(rem == expected for rem in durations)

    effect_list = world.component_for_entity(target_regiment, EffectList)
    assert not effect_list.effect_entities
    final_regiment: Regiment = world.component_for_entity(target_regiment, Regiment)
    assert pytest.approx(final_regiment.morale) == base_morale
