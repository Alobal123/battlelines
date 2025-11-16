from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_EXECUTE,
    EVENT_TILE_BANK_DEPLETED,
    EVENT_HEALTH_DAMAGE,
)
from ecs.world import create_world
from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.tile_bank import TileBank
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.systems.ability_resolution_system import AbilityResolutionSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.deplete_effect_system import DepleteEffectSystem
from ecs.systems.effects.damage_effect_system import DamageEffectSystem
from ecs.factories.enemies import create_enemy_undead_florist


def _find_human_entity(world):
    return next(ent for ent, _ in world.get_component(HumanAgent))


def _find_enemy_entity(world):
    return next(ent for ent, _ in world.get_component(RuleBasedAgent))


def _find_ability(world, owner_ent: int, ability_name: str) -> int:
    owner_comp = world.component_for_entity(owner_ent, AbilityListOwner)
    for ability_ent in owner_comp.ability_entities:
        ability = world.component_for_entity(ability_ent, Ability)
        if ability.name == ability_name:
            return ability_ent
    raise AssertionError(f"Ability '{ability_name}' not found for entity {owner_ent}")


def test_undead_florist_has_touch_of_undead():
    bus = EventBus()
    world = create_world(bus)

    florist_entity = create_enemy_undead_florist(world)
    owner_comp = world.component_for_entity(florist_entity, AbilityListOwner)
    ability_names = {
        world.component_for_entity(ability_ent, Ability).name for ability_ent in owner_comp.ability_entities
    }
    assert {"touch_of_undead", "poisoned_flower"}.issubset(ability_names)


def test_touch_of_undead_depletes_each_mana_type():
    bus = EventBus()
    world = create_world(bus)

    EffectLifecycleSystem(world, bus)
    DepleteEffectSystem(world, bus)
    DamageEffectSystem(world, bus)
    AbilityResolutionSystem(world, bus)

    human_ent = _find_human_entity(world)
    enemy_ent = _find_enemy_entity(world)
    ability_ent = _find_ability(world, enemy_ent, "touch_of_undead")

    human_bank: TileBank = world.component_for_entity(human_ent, TileBank)
    human_bank.counts.clear()
    human_bank.counts.update({"blood": 2, "spirit": 1, "hex": 0, "nature": 3})

    depleted_events = []
    bus.subscribe(EVENT_TILE_BANK_DEPLETED, lambda sender, **payload: depleted_events.append(payload))
    damage_events = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda sender, **payload: damage_events.append(payload))

    pending = PendingAbilityTarget(
        ability_entity=ability_ent,
        owner_entity=enemy_ent,
        row=None,
        col=None,
        target_entity=enemy_ent,
    )

    bus.emit(
        EVENT_ABILITY_EXECUTE,
        ability_entity=ability_ent,
        owner_entity=enemy_ent,
        pending=pending,
    )

    assert human_bank.counts["blood"] == 1
    assert human_bank.counts["spirit"] == 0
    assert human_bank.counts["nature"] == 2
    assert human_bank.counts["hex"] == 0

    assert depleted_events, "Touch of Undead should emit a depletion event"
    last = depleted_events[-1]
    assert last["owner_entity"] == human_ent
    assert last["mode"] == "all"
    assert last["deltas"] == {"blood": 1, "spirit": 1, "nature": 1}
    assert last.get("reason") == "touch_of_undead"

    assert damage_events, "Touch of Undead should deal damage equal to the depletion"
    damage_payload = damage_events[-1]
    assert damage_payload["target_entity"] == human_ent
    assert damage_payload["amount"] == 3
    assert damage_payload.get("reason") == "touch_of_undead"