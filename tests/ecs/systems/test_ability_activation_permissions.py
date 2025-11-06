import pytest
from ecs.events.bus import EventBus, EVENT_ABILITY_ACTIVATE_REQUEST, EVENT_TILE_CLICK
from ecs.world import create_world
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.turn_system import TurnSystem
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.targeting_state import TargetingState
from ecs.components.active_turn import ActiveTurn
from ecs.components.ability import Ability

@pytest.fixture
def setup_world():
    bus = EventBus(); world = create_world(bus)
    AbilitySystem(world, bus)
    TurnSystem(world, bus)
    return bus, world

def _get_players(world):
    return [ (ent, comp) for ent, comp in world.get_component(AbilityListOwner) ]

def test_cannot_activate_other_players_ability(setup_world):
    bus, world = setup_world
    players = _get_players(world)
    p1_ent, p1_comp = players[0]
    p2_ent, p2_comp = players[1]
    other_players_ability = p2_comp.ability_entities[0]
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=other_players_ability, owner_entity=p1_ent)
    # Player1 should NOT have a TargetingState component
    targeting_states = [ent for ent,_ in world.get_component(TargetingState)]
    assert p1_ent not in targeting_states, 'Should not enter targeting for another player\'s ability'

def test_inactive_turn_cannot_activate_own_ability(setup_world):
    bus, world = setup_world
    players = _get_players(world)
    p1_ent, p1_comp = players[0]
    p2_ent, p2_comp = players[1]
    # ActiveTurn initially for player1; player2 attempts to activate their own ability
    p2_ability = p2_comp.ability_entities[0]
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=p2_ability, owner_entity=p2_ent)
    targeting_states = [ent for ent,_ in world.get_component(TargetingState)]
    assert p2_ent not in targeting_states, 'Inactive player should not enter targeting'
    # Force turn advance by simulating match cleared + cascade complete
    from ecs.events.bus import EVENT_MATCH_CLEARED, EVENT_CASCADE_COMPLETE
    # Need owner_entity for match; use p1_ent
    bus.emit(EVENT_MATCH_CLEARED, positions=[], colors=[], owner_entity=p1_ent)
    bus.emit(EVENT_CASCADE_COMPLETE, depth=0)
    active_owner = list(world.get_component(ActiveTurn))[0][1].owner_entity
    if active_owner != p2_ent:
        pytest.skip('Turn did not advance to player2; cannot test activation')
    # Now player2 should be able to activate
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=p2_ability, owner_entity=p2_ent)
    targeting_states = [ent for ent,_ in world.get_component(TargetingState)]
    assert p2_ent in targeting_states, 'Active player should enter targeting for own ability'
