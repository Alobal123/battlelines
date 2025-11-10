from ecs.systems.battle import BattleSystem, BattleConfig
from ecs.world import create_world
from ecs.events.bus import EventBus, EVENT_REGIMENT_CLICK, EVENT_BATTLE_RESOLVED
from ecs.components.army_roster import ArmyRoster
from ecs.components.regiment import Regiment
from ecs.components.active_turn import ActiveTurn
from ecs.systems.turn_system import TurnSystem

def test_battle_system_config_defaults():
    bus = EventBus()
    world = create_world(bus)
    system = BattleSystem(world, bus)
    cfg = system.config
    assert cfg.base_morale_damage_per_hit == 3.0
    assert cfg.base_casualty_rate_per_hit == 0.10
    assert cfg.base_hit_chance_percent == 60.0
    assert cfg.hit_bonus_per_combat_skill_difference == 3.0
    assert cfg.hit_bonus_per_readiness_difference == 2.0
    assert cfg.base_frontline_size == 40.0
    assert cfg.minimum_readiness_to_attack == 5.0
    assert cfg.readiness_cost_per_attack == 5.0
    assert cfg.readiness_gain_when_defending == 2.0
    assert cfg.armour_morale_reduction_per_point == 0.06
    assert cfg.armour_casualty_reduction_per_point == 0.08


def test_insufficient_readiness_prevents_attack():
    bus = EventBus()
    world = create_world(bus)
    TurnSystem(world, bus)
    battle = BattleSystem(world, bus)
    owner = world.get_component(ArmyRoster)[0][0]
    roster: ArmyRoster = world.component_for_entity(owner, ArmyRoster)
    active_reg_ent = roster.active_regiment()
    active_reg = world.component_for_entity(active_reg_ent, Regiment)
    active_reg.battle_readiness = 4
    events = []
    bus.subscribe(EVENT_BATTLE_RESOLVED, lambda s, **k: events.append(k))
    bus.emit(EVENT_REGIMENT_CLICK, owner_entity=owner, regiment_entity=active_reg_ent)
    assert not events, "Battle should not resolve when readiness below threshold"
    active_reg.battle_readiness = 5
    bus.emit(EVENT_REGIMENT_CLICK, owner_entity=owner, regiment_entity=active_reg_ent)
    assert events, "Battle should resolve once readiness meets threshold"


def test_combat_spends_readiness_for_both_units():
    bus = EventBus()
    world = create_world(bus)
    TurnSystem(world, bus)
    BattleSystem(world, bus)
    rosters = list(world.get_component(ArmyRoster))
    assert len(rosters) >= 2
    attacker_owner = rosters[0][0]
    defender_owner = rosters[1][0]
    attacker_roster: ArmyRoster = world.component_for_entity(attacker_owner, ArmyRoster)
    defender_roster: ArmyRoster = world.component_for_entity(defender_owner, ArmyRoster)
    attacker_entity = attacker_roster.active_regiment()
    defender_entity = defender_roster.active_regiment()
    attacker_reg = world.component_for_entity(attacker_entity, Regiment)
    defender_reg = world.component_for_entity(defender_entity, Regiment)
    attacker_reg.battle_readiness = 10
    defender_reg.battle_readiness = 10
    events = []
    bus.subscribe(EVENT_BATTLE_RESOLVED, lambda s, **k: events.append(k))
    bus.emit(EVENT_REGIMENT_CLICK, owner_entity=attacker_owner, regiment_entity=attacker_entity)
    assert events, "Battle should fire with sufficient readiness"
    assert attacker_reg.battle_readiness == 5
    assert defender_reg.battle_readiness == 5
    events.clear()
    attacker_reg.battle_readiness = 5
    defender_reg.battle_readiness = 4
    bus.emit(EVENT_REGIMENT_CLICK, owner_entity=attacker_owner, regiment_entity=attacker_entity)
    assert events, "Second battle should still resolve"
    assert attacker_reg.battle_readiness == 0
    assert defender_reg.battle_readiness == 0
