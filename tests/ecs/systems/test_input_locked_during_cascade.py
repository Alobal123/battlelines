import pytest
from ecs.events.bus import EventBus, EVENT_CASCADE_STEP, EVENT_CASCADE_COMPLETE, EVENT_TILE_CLICK, EVENT_ABILITY_ACTIVATE_REQUEST
from ecs.world import create_world
from ecs.systems.board import BoardSystem
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.tile_bank_system import TileBankSystem
from ecs.systems.turn_system import TurnSystem
from ecs.components.targeting_state import TargetingState

@pytest.fixture
def setup_env():
    bus = EventBus(); world = create_world(bus)
    board = BoardSystem(world, bus, 5, 5)
    AbilitySystem(world, bus)
    TileBankSystem(world, bus)
    TurnSystem(world, bus)
    return bus, world, board

def test_tile_click_ignored_during_cascade(setup_env):
    bus, world, board = setup_env
    # Start cascade (simulate depth step)
    bus.emit(EVENT_CASCADE_STEP, depth=1, positions=[(0,0)])
    bus.emit(EVENT_TILE_CLICK, row=0, col=0)
    assert board.selected is None, 'Selection should be blocked while cascade active'
    bus.emit(EVENT_CASCADE_COMPLETE, depth=1)
    bus.emit(EVENT_TILE_CLICK, row=0, col=0)
    assert board.selected == (0,0), 'Selection should work again after cascade complete'

def test_ability_activation_blocked_during_cascade(setup_env):
    bus, world, board = setup_env
    owners = list(world.get_component(type(board)))  # bogus retrieval to ensure variable unused
    # Acquire first owner ability
    from ecs.components.ability_list_owner import AbilityListOwner
    owners = list(world.get_component(AbilityListOwner))
    owner_ent, owner_comp = owners[0]
    ability_ent = owner_comp.ability_entities[0]
    bus.emit(EVENT_CASCADE_STEP, depth=1, positions=[(0,0)])
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=ability_ent, owner_entity=owner_ent)
    targeting = list(world.get_component(TargetingState))
    assert not targeting, 'TargetingState should not be created during cascade'
    # After cascade complete activation should succeed
    bus.emit(EVENT_CASCADE_COMPLETE, depth=1)
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=ability_ent, owner_entity=owner_ent)
    targeting = list(world.get_component(TargetingState))
    assert targeting, 'TargetingState should be created after cascade ends'
