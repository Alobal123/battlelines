from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.ability_cooldown import AbilityCooldown
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_ACTIVATE_REQUEST,
    EVENT_ABILITY_EXECUTE,
    EVENT_TILE_BANK_SPEND_REQUEST,
    EVENT_TURN_ADVANCED,
)
from ecs.systems.ability_cooldown_system import AbilityCooldownSystem
from ecs.systems.ability_targeting_system import AbilityTargetingSystem


def _build_ability(world: World, cooldown: int) -> tuple[int, int]:
    ability_entity = world.create_entity(
        Ability(name="test", kind="active", cost={}, cooldown=cooldown),
        AbilityTarget(target_type="self", max_targets=0),
        AbilityCooldown(),
    )
    owner_entity = world.create_entity(AbilityListOwner(ability_entities=[ability_entity]))
    return ability_entity, owner_entity


def test_ability_cooldown_set_and_progresses():
    world = World()
    bus = EventBus()
    ability_entity, owner_entity = _build_ability(world, cooldown=2)
    AbilityCooldownSystem(world, bus)

    bus.emit(EVENT_ABILITY_EXECUTE, ability_entity=ability_entity, owner_entity=owner_entity, pending=None)
    cooldown_state = world.component_for_entity(ability_entity, AbilityCooldown)
    assert cooldown_state.remaining_turns == 2

    # Different owner turn should not tick cooldown
    bus.emit(EVENT_TURN_ADVANCED, previous_owner=owner_entity, new_owner=owner_entity + 1)
    assert cooldown_state.remaining_turns == 2

    # Owner's next turn reduces cooldown
    bus.emit(EVENT_TURN_ADVANCED, previous_owner=owner_entity + 1, new_owner=owner_entity)
    assert cooldown_state.remaining_turns == 1

    bus.emit(EVENT_TURN_ADVANCED, previous_owner=owner_entity, new_owner=owner_entity)
    assert cooldown_state.remaining_turns == 0


def test_activation_blocked_when_on_cooldown():
    world = World()
    bus = EventBus()
    ability_entity, owner_entity = _build_ability(world, cooldown=1)
    AbilityCooldownSystem(world, bus)
    AbilityTargetingSystem(world, bus)

    captured: list[dict] = []

    def _capture(sender, **payload):
        captured.append(payload)

    bus.subscribe(EVENT_TILE_BANK_SPEND_REQUEST, _capture)

    # Ability ready: spend request emitted
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=ability_entity, owner_entity=owner_entity)
    assert captured, "Ready ability should emit spend request"

    # Set cooldown and ensure activation is blocked
    captured.clear()
    cooldown_state = world.component_for_entity(ability_entity, AbilityCooldown)
    cooldown_state.remaining_turns = 1
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=ability_entity, owner_entity=owner_entity)
    assert not captured, "Ability on cooldown should not emit spend request"
