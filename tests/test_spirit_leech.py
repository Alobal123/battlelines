from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_EXECUTE,
    EVENT_HEALTH_DAMAGE,
    EVENT_MANA_DRAIN,
    EVENT_TILE_BANK_CHANGED,
    EVENT_TILE_BANK_GAINED,
)
from world import create_world
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.tile_bank import TileBank
from ecs.components.health import Health
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.factories.abilities import create_ability_by_name
from ecs.systems.health_system import HealthSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.damage_effect_system import DamageEffectSystem
from ecs.systems.effects.mana_drain_effect_system import ManaDrainEffectSystem
from ecs.systems.ability_resolution_system import AbilityResolutionSystem


def _find_entity(world, component_type):
    return next(ent for ent, _ in world.get_component(component_type))


def _find_bank_entity(world, owner_entity):
    for bank_entity, bank in world.get_component(TileBank):
        if bank.owner_entity == owner_entity:
            return bank_entity, bank
    raise AssertionError(f"Tile bank for owner {owner_entity} not found")


def test_spirit_leech_drains_mana_and_deals_damage():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)

    HealthSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    DamageEffectSystem(world, bus)
    ManaDrainEffectSystem(world, bus)
    AbilityResolutionSystem(world, bus)

    human_ent = _find_entity(world, HumanAgent)
    enemy_ent = _find_entity(world, RuleBasedAgent)

    owner_comp: AbilityListOwner = world.component_for_entity(human_ent, AbilityListOwner)
    spirit_leech_entity = create_ability_by_name(world, "spirit_leech")
    owner_comp.ability_entities.append(spirit_leech_entity)

    bank_entity, enemy_bank = _find_bank_entity(world, enemy_ent)
    owner_bank_entity, owner_bank = _find_bank_entity(world, human_ent)
    enemy_bank.counts.clear()
    enemy_bank.counts.update({"spirit": 4, "blood": 1})

    initial_owner_counts = owner_bank.counts.copy()

    enemy_health: Health = world.component_for_entity(enemy_ent, Health)
    initial_enemy_hp = enemy_health.current

    drain_events = []
    damage_events = []
    bank_change_events = []
    gain_events = []

    bus.subscribe(EVENT_MANA_DRAIN, lambda sender, **payload: drain_events.append(payload))
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda sender, **payload: damage_events.append(payload))
    bus.subscribe(EVENT_TILE_BANK_CHANGED, lambda sender, **payload: bank_change_events.append(payload))
    bus.subscribe(EVENT_TILE_BANK_GAINED, lambda sender, **payload: gain_events.append(payload))

    pending = PendingAbilityTarget(
        ability_entity=spirit_leech_entity,
        owner_entity=human_ent,
        row=None,
        col=None,
        target_entity=human_ent,
    )

    bus.emit(
        EVENT_ABILITY_EXECUTE,
        ability_entity=spirit_leech_entity,
        owner_entity=human_ent,
        pending=pending,
    )

    assert enemy_bank.counts["spirit"] == 2
    assert enemy_bank.counts["blood"] == 1
    assert owner_bank.counts.get("spirit", 0) == initial_owner_counts.get("spirit", 0) + 2

    assert drain_events, "Spirit Leech should emit a mana drain event"
    drain_payload = drain_events[-1]
    assert drain_payload["target_entity"] == enemy_ent
    assert drain_payload["amount"] == 2
    assert drain_payload["breakdown"] == {"spirit": 2}
    assert drain_payload.get("gained") == {"spirit": 2}
    assert drain_payload.get("reason") == "spirit_leech"
    assert drain_payload.get("mode") == "random_eligible"

    assert bank_change_events, "Spirit Leech should notify tile bank changes"
    enemy_change = next(payload for payload in bank_change_events if payload["entity"] == bank_entity)
    assert enemy_change["counts"]["spirit"] == 2
    owner_change = next(payload for payload in bank_change_events if payload["entity"] == owner_bank_entity)
    assert owner_change["counts"]["spirit"] == owner_bank.counts["spirit"]

    assert gain_events, "Expected tile bank gain event for mana drain"
    gain_payload = gain_events[-1]
    assert gain_payload["owner_entity"] == human_ent
    assert gain_payload["bank_entity"] == owner_bank_entity
    assert gain_payload["type_name"] == "spirit"
    assert gain_payload["amount"] == 2

    assert damage_events, "Spirit Leech should deal damage"
    damage_payload = damage_events[-1]
    assert damage_payload["target_entity"] == enemy_ent
    assert damage_payload["amount"] == 2
    assert damage_payload.get("reason") == "spirit_leech"

    assert enemy_health.current == initial_enemy_hp - 2
