import pytest
from ecs.events.bus import EventBus, EVENT_ABILITY_ACTIVATE_REQUEST, EVENT_TILE_BANK_SPENT, EVENT_ABILITY_TARGET_SELECTED, EVENT_TILE_CLICK, EVENT_CASCADE_COMPLETE
from ecs.world import create_world
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.turn_system import TurnSystem
from ecs.systems.tile_bank_system import TileBankSystem
from ecs.components.active_turn import ActiveTurn
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.ability import Ability
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.targeting_state import TargetingState

# This test ensures that an ability that produces a board change but NO matches still ends the turn.
# We'll trigger tactical_shift on a tile color that after conversion creates no matches.

@pytest.fixture
def setup_world():
    bus = EventBus(); world = create_world(bus)
    AbilitySystem(world, bus)
    TileBankSystem(world, bus)
    turn = TurnSystem(world, bus)
    return bus, world, turn

def _activate_first_ability(bus, world):
    owners = list(world.get_component(AbilityListOwner))
    owner_ent, owner_comp = owners[0]
    ability_ent = owner_comp.ability_entities[0]  # tactical_shift
    # Enter targeting; spend will occur after tile click (simulated)
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=ability_ent, owner_entity=owner_ent)
    return owner_ent, ability_ent

def test_ability_without_match_rotates_turn(setup_world):
    bus, world, turn = setup_world
    owners = [ent for ent,_ in world.get_component(AbilityListOwner)]
    assert len(owners) >= 2
    initial_active = list(world.get_component(ActiveTurn))[0][1].owner_entity
    owner_ent, ability_ent = _activate_first_ability(bus, world)
    # Select target -> triggers spend request; simulate spend success afterwards
    bus.emit(EVENT_TILE_CLICK, row=0, col=0)
    ability = world.component_for_entity(ability_ent, Ability)
    bus.emit(EVENT_TILE_BANK_SPENT, entity=owner_ent, ability_entity=ability_ent, cost=ability.cost)
    new_active = list(world.get_component(ActiveTurn))[0][1].owner_entity
    assert new_active != initial_active, 'Turn should advance after ability resolution/cascade completion'
