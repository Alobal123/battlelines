from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_EXECUTE,
    EVENT_EFFECT_APPLIED,
)
from world import create_world
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.board_position import BoardPosition
from ecs.components.health import Health
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.tile import TileType
from ecs.components.tile_bank import TileBank
from ecs.components.active_switch import ActiveSwitch
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.factories.abilities import create_ability_by_name
from ecs.systems.ability_resolution_system import AbilityResolutionSystem
from ecs.systems.board import BoardSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.damage_effect_system import DamageEffectSystem
from ecs.systems.health_system import HealthSystem
from ecs.systems.effects.tile_sacrifice_effect_system import TileSacrificeEffectSystem
from ecs.systems.tile_bank_system import TileBankSystem


def _setup_core_systems(world, bus):
    HealthSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    DamageEffectSystem(world, bus)
    TileSacrificeEffectSystem(world, bus)
    TileBankSystem(world, bus)
    AbilityResolutionSystem(world, bus)


def _human_entity(world):
    return next(entity for entity, _ in world.get_component(HumanAgent))


def _enemy_entity(world):
    return next(entity for entity, _ in world.get_component(RuleBasedAgent))


def _set_column_types(world, column_index, type_names):
    for entity, position in world.get_component(BoardPosition):
        if position.col != column_index:
            continue
        if position.row >= len(type_names):
            continue
        tile = world.component_for_entity(entity, TileType)
        tile.type_name = type_names[position.row]
        switch = world.component_for_entity(entity, ActiveSwitch)
        switch.active = True


def _activate_blood_sacrifice(bus, ability_entity, owner_entity, row, col):
    pending = PendingAbilityTarget(
        ability_entity=ability_entity,
        owner_entity=owner_entity,
        row=row,
        col=col,
        target_entity=None,
    )
    bus.emit(
        EVENT_ABILITY_EXECUTE,
        ability_entity=ability_entity,
        owner_entity=owner_entity,
        pending=pending,
    )


def test_blood_sacrifice_triples_tile_gain_and_leaves_hole():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    BoardSystem(world, bus, rows=4, cols=1)
    _setup_core_systems(world, bus)

    owner = _human_entity(world)
    ability_owner: AbilityListOwner = world.component_for_entity(owner, AbilityListOwner)
    blood_sacrifice = create_ability_by_name(world, "blood_sacrifice")
    ability_owner.ability_entities.append(blood_sacrifice)

    _set_column_types(world, 0, ["blood", "nature", "hex", "spirit"])

    bank_entity = next(ent for ent, bank in world.get_component(TileBank) if bank.owner_entity == owner)
    bank: TileBank = world.component_for_entity(bank_entity, TileBank)
    bank.counts.clear()

    effects: list[dict] = []
    bus.subscribe(EVENT_EFFECT_APPLIED, lambda s, **k: effects.append(k))

    _activate_blood_sacrifice(bus, blood_sacrifice, owner, row=0, col=0)

    assert bank.counts.get("blood", 0) == 3
    assert any(event.get("slug") == "tile_sacrifice" for event in effects)

    # Bottom tile should now hold the previous row 1 type, and the top remains inactive (no refill yet).
    tiles_by_row = {
        position.row: (entity, world.component_for_entity(entity, TileType), world.component_for_entity(entity, ActiveSwitch))
        for entity, position in world.get_component(BoardPosition)
        if position.col == 0
    }
    assert tiles_by_row[0][1].type_name == "nature"
    assert tiles_by_row[3][2].active is False


def test_blood_sacrifice_witchfire_damage_targets_enemy():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    BoardSystem(world, bus, rows=4, cols=1)
    _setup_core_systems(world, bus)

    owner = _human_entity(world)
    enemy = _enemy_entity(world)
    ability_owner: AbilityListOwner = world.component_for_entity(owner, AbilityListOwner)
    blood_sacrifice = create_ability_by_name(world, "blood_sacrifice")
    ability_owner.ability_entities.append(blood_sacrifice)

    _set_column_types(world, 0, ["witchfire", "nature", "nature", "nature"])

    enemy_health: Health = world.component_for_entity(enemy, Health)
    owner_health: Health = world.component_for_entity(owner, Health)
    enemy_initial = enemy_health.current
    owner_initial = owner_health.current

    _activate_blood_sacrifice(bus, blood_sacrifice, owner, row=0, col=0)

    assert enemy_health.current == enemy_initial - 3
    assert owner_health.current == owner_initial

    bank_entity = next(ent for ent, bank in world.get_component(TileBank) if bank.owner_entity == owner)
    bank: TileBank = world.component_for_entity(bank_entity, TileBank)
    assert bank.counts.get("witchfire", 0) == 3
