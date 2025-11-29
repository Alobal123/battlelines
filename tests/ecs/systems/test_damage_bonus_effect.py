import pytest

from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_ACTIVATE_REQUEST,
    EVENT_HEALTH_DAMAGE,
    EVENT_TILE_BANK_SPENT,
    EVENT_TURN_ADVANCED,
)
from world import create_world
from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.effect import Effect
from ecs.components.effect_duration import EffectDuration
from ecs.components.effect_list import EffectList
from ecs.components.ability_effect import AbilityEffects
from ecs.components.active_turn import ActiveTurn
from ecs.components.turn_order import TurnOrder
from ecs.components.ability_cooldown import AbilityCooldown
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.ability_targeting_system import AbilityTargetingSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.damage_effect_system import DamageEffectSystem
from ecs.systems.effects.heal_effect_system import HealEffectSystem
from ecs.systems.tile_bank_system import TileBankSystem
from ecs.systems.turn_system import TurnSystem

from tests.helpers import grant_player_abilities


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
    grant_player_abilities(world, ("savagery", "blood_bolt"))
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


def test_savagery_applies_damage_bonus_effect(setup_world):
    bus, world = setup_world
    owner_ent, ability_ent = _find_player_ability(world, "savagery")
    ability_effects = world.component_for_entity(ability_ent, AbilityEffects)
    spec = ability_effects.effects[0] if ability_effects.effects else None
    _activate_self_ability(bus, world, owner_ent, ability_ent)
    effect_ids = _damage_bonus_effects(world, owner_ent)
    assert effect_ids, "Savagery did not apply damage bonus effect"
    effect_entity = effect_ids[0]
    duration = world.component_for_entity(effect_entity, EffectDuration)
    if spec and spec.turns is not None:
        assert duration.remaining_turns == spec.turns
    else:
        assert duration.remaining_turns > 0


def test_savagery_damage_bonus_applies_and_expires(setup_world):
    bus, world = setup_world
    owner_ent, savagery_ent = _find_player_ability(world, "savagery")
    _, blood_bolt_ent = _find_player_ability(world, "blood_bolt")
    damage_events: list[dict] = []
    bus.subscribe(
        EVENT_HEALTH_DAMAGE,
        lambda sender, **payload: damage_events.append(dict(payload)),
    )
    savagery_effects_comp = world.component_for_entity(savagery_ent, AbilityEffects)
    savagery_spec = next((spec for spec in savagery_effects_comp.effects if spec.slug == "damage_bonus"), None)
    bonus_amount = 0
    if savagery_spec is not None:
        try:
            bonus_amount = int(savagery_spec.metadata.get("bonus", 0))
        except (TypeError, ValueError):
            bonus_amount = 0
    _activate_self_ability(bus, world, owner_ent, savagery_ent)
    initial_effects = _damage_bonus_effects(world, owner_ent)
    # Wait for cooldown (2 turns) before reusing Savagery
    owners = [ent for ent, _ in world.get_component(AbilityListOwner) if ent != owner_ent]
    opponent_ent = owners[0] if owners else owner_ent
    for _ in range(2):
        bus.emit(EVENT_TURN_ADVANCED, previous_owner=owner_ent, new_owner=opponent_ent)
        _force_active_owner(world, opponent_ent)
        bus.emit(EVENT_TURN_ADVANCED, previous_owner=opponent_ent, new_owner=owner_ent)
        _force_active_owner(world, owner_ent)
    before_second = _damage_bonus_effects(world, owner_ent)
    assert before_second == initial_effects
    cooldown_state = world.component_for_entity(savagery_ent, AbilityCooldown)
    assert cooldown_state.remaining_turns == 0
    _activate_self_ability(bus, world, owner_ent, savagery_ent)
    assert cooldown_state.remaining_turns == 2
    savagery_effects = _damage_bonus_effects(world, owner_ent)
    assert len(savagery_effects) >= 2, "Repeated Savagery casts should stack separate damage bonus effects"
    existing_effects = set(initial_effects)
    effect_turns = savagery_spec.turns if savagery_spec and savagery_spec.turns is not None else 0
    for effect_entity in savagery_effects:
        duration_comp = world.component_for_entity(effect_entity, EffectDuration)
        assert duration_comp.remaining_turns > 0
        if effect_turns and effect_entity not in existing_effects:
            assert duration_comp.remaining_turns == effect_turns
    damage_events.clear()
    _force_active_owner(world, owner_ent)
    _activate_self_ability(bus, world, owner_ent, blood_bolt_ent)
    assert damage_events, "Blood Bolt did not deal damage"
    amounts = [event["amount"] for event in damage_events]
    blood_bolt_effects = world.component_for_entity(blood_bolt_ent, AbilityEffects)
    blood_bolt_ability = world.component_for_entity(blood_bolt_ent, Ability)
    self_damage = blood_bolt_ability.params.get("self_damage")
    opponent_damage = blood_bolt_ability.params.get("opponent_damage")
    if self_damage is None or opponent_damage is None:
        for spec in blood_bolt_effects.effects:
            if spec.target == "self" and spec.metadata.get("amount") is not None:
                self_damage = int(spec.metadata["amount"])
            if spec.target == "opponent" and spec.metadata.get("amount") is not None:
                opponent_damage = int(spec.metadata["amount"])
    assert self_damage is not None and opponent_damage is not None
    total_bonus = bonus_amount * len(savagery_effects)
    assert amounts == [self_damage + total_bonus, opponent_damage + total_bonus]
    for _ in range(effect_turns or 0):
        bus.emit(EVENT_TURN_ADVANCED, previous_owner=owner_ent, new_owner=None)
    if effect_turns:
        assert not _damage_bonus_effects(world, owner_ent), "Damage bonus effects should expire after their duration"
    damage_events.clear()
    _force_active_owner(world, owner_ent)
    _activate_self_ability(bus, world, owner_ent, blood_bolt_ent)
    amounts = [event["amount"] for event in damage_events]
    assert amounts == [self_damage, opponent_damage]