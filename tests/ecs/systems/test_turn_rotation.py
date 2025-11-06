import pytest
from ecs.events.bus import EventBus, EVENT_MATCH_CLEARED, EVENT_CASCADE_COMPLETE
from ecs.world import create_world
from ecs.systems.turn_system import TurnSystem
from ecs.components.turn_order import TurnOrder
from ecs.components.active_turn import ActiveTurn
from ecs.components.ability_list_owner import AbilityListOwner

@pytest.fixture
def setup_world():
    bus = EventBus()
    world = create_world(bus)
    turn_system = TurnSystem(world, bus)
    return bus, world, turn_system


def test_initial_active_owner(setup_world):
    bus, world, turn_system = setup_world
    owners = [ent for ent,_ in world.get_component(AbilityListOwner)]
    active_list = list(world.get_component(ActiveTurn))
    assert active_list, 'ActiveTurn should be initialized'
    assert active_list[0][1].owner_entity == owners[0]


def test_rotation_after_cascade_complete(setup_world):
    bus, world, turn_system = setup_world
    owners = [ent for ent,_ in world.get_component(AbilityListOwner)]
    assert len(owners) >= 2
    active_before = list(world.get_component(ActiveTurn))[0][1].owner_entity
    # Emit match cleared (simulate part of cascade) -> should NOT rotate yet
    bus.emit(EVENT_MATCH_CLEARED, positions=[], colors=[], owner_entity=active_before)
    active_mid = list(world.get_component(ActiveTurn))[0][1].owner_entity
    assert active_mid == active_before, 'Active should remain until cascade completes'
    # Emit cascade complete -> now rotation should occur
    bus.emit(EVENT_CASCADE_COMPLETE)
    active_after = list(world.get_component(ActiveTurn))[0][1].owner_entity
    assert active_after == owners[1], 'Active should advance only after cascade completion'
    # Second cycle
    bus.emit(EVENT_MATCH_CLEARED, positions=[], colors=[], owner_entity=active_after)
    bus.emit(EVENT_CASCADE_COMPLETE)
    active_wrap = list(world.get_component(ActiveTurn))[0][1].owner_entity
    assert active_wrap == owners[0], 'Rotation should wrap to first owner after second cascade'
