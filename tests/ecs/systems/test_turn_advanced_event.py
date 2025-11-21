import pytest
from ecs.events.bus import EventBus, EVENT_MATCH_CLEARED, EVENT_CASCADE_COMPLETE, EVENT_TURN_ADVANCED, EVENT_ABILITY_ACTIVATE_REQUEST, EVENT_TILE_CLICK, EVENT_TILE_BANK_SPENT
from ecs.world import create_world
from ecs.systems.turn_system import TurnSystem
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.ability_targeting_system import AbilityTargetingSystem
from ecs.systems.tile_bank_system import TileBankSystem
from ecs.systems.board import BoardSystem
from ecs.systems.match import MatchSystem
from ecs.systems.match_resolution import MatchResolutionSystem
from ecs.systems.animation import AnimationSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.board_clear_effect_system import BoardClearEffectSystem
from ecs.systems.effects.board_transform_effect_system import BoardTransformEffectSystem
from ecs.components.active_turn import ActiveTurn
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.human_agent import HumanAgent
from ecs.components.ability import Ability
from ecs.components.tile_bank import TileBank
from ecs.components.board_position import BoardPosition
from ecs.components.tile import TileType

from tests.helpers import grant_player_abilities

@pytest.fixture
def setup_world():
    bus = EventBus(); world = create_world(bus)
    TurnSystem(world, bus)
    AbilityTargetingSystem(world, bus)
    AbilitySystem(world, bus)
    TileBankSystem(world, bus)
    BoardSystem(world, bus)
    MatchSystem(world, bus)
    AnimationSystem(world, bus)
    MatchResolutionSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    BoardClearEffectSystem(world, bus)
    BoardTransformEffectSystem(world, bus)
    grant_player_abilities(world, ("tactical_shift", "savagery"))
    return bus, world

def test_turn_advanced_on_cascade_complete(setup_world):
    bus, world = setup_world
    owners = _ordered_owner_ids(world)
    assert len(owners) >= 2
    events = []
    bus.subscribe(EVENT_TURN_ADVANCED, lambda s, **k: events.append(k))
    # Simulate rotation via cascade completion path
    bus.emit(EVENT_MATCH_CLEARED, positions=[], colors=[])
    # Pending rotation set; not advanced yet
    assert not events
    bus.emit(EVENT_CASCADE_COMPLETE, depth=1)
    assert events, 'EVENT_TURN_ADVANCED not emitted after cascade completion'
    assert events[-1]['new_owner'] == owners[1]

def _apply_board_pattern(world, overrides: dict[tuple[int, int], str]):
    base = ['blood', 'secrets', 'spirit', 'witchfire']
    alt = ['secrets', 'spirit', 'witchfire', 'blood']
    for ent, pos in world.get_component(BoardPosition):
        tile = world.component_for_entity(ent, TileType)
        seq = base if (pos.row % 2 == 0) else alt
        tile.type_name = seq[pos.col % len(seq)]
    for (row, col), type_name in overrides.items():
        for ent, pos in world.get_component(BoardPosition):
            if pos.row == row and pos.col == col:
                tile = world.component_for_entity(ent, TileType)
                tile.type_name = type_name
                break

def test_turn_advanced_on_ability_no_cascade(setup_world):
    bus, world = setup_world
    events = []
    bus.subscribe(EVENT_TURN_ADVANCED, lambda s, **k: events.append(k))
    owners = _ordered_owners(world)
    owner_ent, owner_comp = owners[0]
    initial_active = list(world.get_component(ActiveTurn))[0][1].owner_entity
    ability_ent = owner_comp.ability_entities[0]
    _apply_board_pattern(world, {(0, 0): 'nature'})
    # Activate ability -> targeting
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=ability_ent, owner_entity=owner_ent)
    bus.emit(EVENT_TILE_CLICK, row=0, col=0)
    # Simulate bank spend success (effect application path inside AbilitySystem)
    ability = world.component_for_entity(ability_ent, Ability)
    bus.emit(EVENT_TILE_BANK_SPENT, entity=owner_ent, ability_entity=ability_ent, cost=ability.cost)
    # Ability system will apply effect and TurnSystem should rotate (no matches guaranteed not asserting here)
    assert events, 'EVENT_TURN_ADVANCED not emitted after ability with no cascade'
    owners_ids = [ent for ent, _ in owners]
    assert events[-1]['previous_owner'] in owners_ids


def test_turn_not_advanced_when_ability_preserves_turn(setup_world):
    bus, world = setup_world
    owners = _ordered_owners(world)
    owner_ent, owner_comp = owners[0]
    savagery_ent = next(
        ability_ent
        for ability_ent in owner_comp.ability_entities
        if world.component_for_entity(ability_ent, Ability).name == "savagery"
    )
    savagery_ability = world.component_for_entity(savagery_ent, Ability)
    bank = world.component_for_entity(owner_ent, TileBank)
    initial_cost = {}
    for type_name, amount in savagery_ability.cost.items():
        bank.counts[type_name] = max(bank.counts.get(type_name, 0), amount)
        initial_cost[type_name] = bank.counts[type_name]
    events = []
    bus.subscribe(EVENT_TURN_ADVANCED, lambda s, **k: events.append(k))
    active_before = list(world.get_component(ActiveTurn))[0][1].owner_entity
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=savagery_ent, owner_entity=owner_ent)
    active_after = list(world.get_component(ActiveTurn))[0][1].owner_entity
    assert not events, "Turn should not advance for abilities that preserve the turn"
    assert active_after == active_before, "Active owner should remain unchanged"
    for type_name, previous_amount in initial_cost.items():
        expected_remaining = previous_amount - savagery_ability.cost[type_name]
        assert bank.counts.get(type_name, 0) == expected_remaining, "Ability cost should still be consumed"


def _ordered_owner_ids(world):
    owners = _ordered_owners(world)
    return [ent for ent, _ in owners]


def _ordered_owners(world):
    owners = list(world.get_component(AbilityListOwner))
    human_entities = {ent for ent, _ in world.get_component(HumanAgent)}
    owners.sort(key=lambda pair: (pair[0] not in human_entities, pair[0]))
    return owners
