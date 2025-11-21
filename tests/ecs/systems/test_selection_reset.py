import pytest
from ecs.events.bus import EventBus, EVENT_TILE_CLICK, EVENT_ABILITY_ACTIVATE_REQUEST, EVENT_MATCH_CLEARED, EVENT_CASCADE_COMPLETE
from ecs.world import create_world
from ecs.systems.board import BoardSystem
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.ability_targeting_system import AbilityTargetingSystem
from ecs.systems.turn_system import TurnSystem
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.human_agent import HumanAgent

from tests.helpers import grant_player_abilities

@pytest.fixture
def setup_world():
    bus = EventBus(); world = create_world(bus)
    board = BoardSystem(world, bus)
    AbilityTargetingSystem(world, bus)
    ability = AbilitySystem(world, bus)
    turn = TurnSystem(world, bus)
    grant_player_abilities(world, ("tactical_shift",))
    return bus, world, board

def _first_player(world):
    human_entities = list(world.get_component(HumanAgent))
    assert human_entities, 'No human agent found'
    owner_ent = human_entities[0][0]
    owner_comp = world.component_for_entity(owner_ent, AbilityListOwner)
    return owner_ent, owner_comp

def test_selection_clears_on_target_mode(setup_world):
    bus, world, board = setup_world
    p1_ent, p1_comp = _first_player(world)
    # Select a tile
    bus.emit(EVENT_TILE_CLICK, row=0, col=0)
    assert board.selected == (0,0)
    # Activate ability (player owns ability)
    ability_entity = p1_comp.ability_entities[0]
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=ability_entity, owner_entity=p1_ent)
    # Selection should be cleared
    assert board.selected is None, 'Selection not cleared when entering targeting mode'

def test_selection_clears_on_turn_advance(setup_world):
    bus, world, board = setup_world
    p1_ent, p1_comp = _first_player(world)
    # Select a tile
    bus.emit(EVENT_TILE_CLICK, row=1, col=1)
    assert board.selected == (1,1)
    # Advance turn manually via match cleared + cascade complete
    bus.emit(EVENT_MATCH_CLEARED, positions=[], colors=[], owner_entity=p1_ent)
    bus.emit(EVENT_CASCADE_COMPLETE, depth=0)
    assert board.selected is None, 'Selection not cleared on turn advance'
