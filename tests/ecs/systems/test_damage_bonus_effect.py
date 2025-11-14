import pytest

from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_ACTIVATE_REQUEST,
    EVENT_HEALTH_DAMAGE,
    EVENT_TILE_BANK_SPENT,
    EVENT_TURN_ADVANCED,
)
from ecs.world import create_world
from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.effect import Effect
from ecs.components.effect_duration import EffectDuration
from ecs.components.effect_list import EffectList
from ecs.components.active_turn import ActiveTurn
from ecs.components.turn_order import TurnOrder
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.ability_targeting_system import AbilityTargetingSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.damage_effect_system import DamageEffectSystem
from ecs.systems.effects.heal_effect_system import HealEffectSystem
from ecs.systems.tile_bank_system import TileBankSystem
from ecs.systems.turn_system import TurnSystem


@pytest.fixture
def setup_world():
    bus = EventBus()
    world = create_world(bus)
    AbilityTargetingSystem(world, bus)
    AbilitySystem(world, bus)
    TileBankSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    DamageEffectSystem(world, bus)
    HealEffectSystem(world, bus)
    TurnSystem(world, bus)
    return bus, world


def _find_player_ability(world, ability_name: str) -> tuple[int, int]:
    for owner_ent, owner_comp in world.get_component(AbilityListOwner):
        for ability_ent in owner_comp.ability_entities:
            ability = world.component_for_entity(ability_ent, Ability)
            if ability.name == ability_name:
                return owner_ent, ability_ent
    raise AssertionError(f"Ability '{ability_name}' not found")


def _activate_self_ability(bus: EventBus, world, owner_ent: int, ability_ent: int) -> None:
    ability = world.component_for_entity(ability_ent, Ability)
    bus.emit(
        EVENT_ABILITY_ACTIVATE_REQUEST,
        ability_entity=ability_ent,
        owner_entity=owner_ent,
    )
    bus.emit(
        EVENT_TILE_BANK_SPENT,
        entity=owner_ent,
        ability_entity=ability_ent,
        cost=ability.cost,
    )


def _force_active_owner(world, owner_ent: int) -> None:
    active_turns = list(world.get_component(ActiveTurn))
    if active_turns:
        active_turns[0][1].owner_entity = owner_ent
    turn_orders = list(world.get_component(TurnOrder))
    if turn_orders:
        order = turn_orders[0][1]
        if owner_ent in order.owners:
            order.index = order.owners.index(owner_ent)


def _damage_bonus_effects(world, owner_ent: int) -> list[int]:
    try:
        effect_list = world.component_for_entity(owner_ent, EffectList)
    except KeyError:
        return []
    ids: list[int] = []
    for effect_id in list(effect_list.effect_entities):
        try:
            effect = world.component_for_entity(effect_id, Effect)
        except KeyError:
            continue
        if effect.slug == "damage_bonus":
            ids.append(effect_id)
    return ids


def test_ferality_applies_damage_bonus_effect(setup_world):
    bus, world = setup_world
    owner_ent, ability_ent = _find_player_ability(world, "ferality")
    _activate_self_ability(bus, world, owner_ent, ability_ent)
    effect_ids = _damage_bonus_effects(world, owner_ent)
    assert effect_ids, "Ferality did not apply damage bonus effect"
    effect_entity = effect_ids[0]
    duration = world.component_for_entity(effect_entity, EffectDuration)
    assert duration.remaining_turns == 3


def test_ferality_damage_bonus_applies_and_expires(setup_world):
    bus, world = setup_world
    owner_ent, ferality_ent = _find_player_ability(world, "ferality")
    _, blood_bolt_ent = _find_player_ability(world, "blood_bolt")
    damage_events: list[dict] = []
    bus.subscribe(
        EVENT_HEALTH_DAMAGE,
        lambda sender, **payload: damage_events.append(dict(payload)),
    )
    _activate_self_ability(bus, world, owner_ent, ferality_ent)
    _force_active_owner(world, owner_ent)
    _activate_self_ability(bus, world, owner_ent, ferality_ent)
    ferality_effects = _damage_bonus_effects(world, owner_ent)
    assert len(ferality_effects) == 2, "Ferality stacks should produce two effects"
    damage_events.clear()
    _force_active_owner(world, owner_ent)
    _activate_self_ability(bus, world, owner_ent, blood_bolt_ent)
    assert damage_events, "Blood Bolt did not deal damage"
    amounts = [event["amount"] for event in damage_events]
    assert amounts == [4, 8]
    for _ in range(3):
        bus.emit(EVENT_TURN_ADVANCED, previous_owner=owner_ent, new_owner=None)
    assert not _damage_bonus_effects(world, owner_ent), "Damage bonus effects should expire after three turns"
    damage_events.clear()
    _force_active_owner(world, owner_ent)
    _activate_self_ability(bus, world, owner_ent, blood_bolt_ent)
    amounts = [event["amount"] for event in damage_events]
    assert amounts == [2, 6]