import pytest
from ecs.events.bus import EventBus, EVENT_ABILITY_ACTIVATE_REQUEST, EVENT_TILE_CLICK, EVENT_TILE_BANK_SPENT, EVENT_TURN_ADVANCED, EVENT_CASCADE_COMPLETE, EVENT_CASCADE_STEP
from ecs.world import create_world
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.tile_bank_system import TileBankSystem
from ecs.systems.turn_system import TurnSystem
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.active_turn import ActiveTurn

@pytest.fixture
def setup_world():
    bus = EventBus(); world = create_world(bus)
    AbilitySystem(world, bus)
    TileBankSystem(world, bus)
    TurnSystem(world, bus)
    return bus, world

def _activate_crimson_pulse(bus, world):
    owners = list(world.get_component(AbilityListOwner))
    owner_ent, owner_comp = owners[0]
    from ecs.components.ability import Ability
    ability_ent = None
    for ent, ability in world.get_component(Ability):
        if ability.name == 'crimson_pulse' and ent in owner_comp.ability_entities:
            ability_ent = ent
            break
    assert ability_ent is not None, 'crimson_pulse ability not found'
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=ability_ent, owner_entity=owner_ent)
    # Click target (0,0)
    bus.emit(EVENT_TILE_CLICK, row=0, col=0)
    # Spend cost success
    ability = world.component_for_entity(ability_ent, Ability)
    bus.emit(EVENT_TILE_BANK_SPENT, entity=owner_ent, ability_entity=ability_ent, cost=ability.cost)
    return owner_ent, ability_ent

def test_crimson_pulse_turn_advances_via_depth_zero_cascade_complete(setup_world):
    bus, world = setup_world
    active_before = list(world.get_component(ActiveTurn))[0][1].owner_entity
    events = []
    cascade_events = []
    bus.subscribe(EVENT_CASCADE_COMPLETE, lambda s, **k: cascade_events.append(k))
    bus.subscribe(EVENT_TURN_ADVANCED, lambda s, **k: events.append(k))
    _activate_crimson_pulse(bus, world)
    assert events, 'Turn should advance after ability resolution'
    assert cascade_events, 'Expected cascade_complete depth=0 event'
    assert cascade_events[-1].get('depth') == 0
    assert events[-1]['previous_owner'] == active_before
