import pytest
from ecs.events.bus import EventBus, EVENT_MOUSE_PRESS, EVENT_ABILITY_ACTIVATE_REQUEST, EVENT_ABILITY_TARGET_CANCELLED
from ecs.world import create_world
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.ability_targeting_system import AbilityTargetingSystem
from ecs.systems.board import BoardSystem
from ecs.systems.render import RenderSystem
from ecs.components.targeting_state import TargetingState
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.human_agent import HumanAgent

from tests.helpers import grant_player_abilities

@pytest.fixture
def setup_world():
    bus = EventBus()
    world = create_world(bus)
    grant_player_abilities(world, ("tactical_shift",))
    class DummyWindow:
        width = 800
        height = 600
    window = DummyWindow()
    AbilityTargetingSystem(world, bus)
    ability_system = AbilitySystem(world, bus)
    board_system = BoardSystem(world, bus)
    render_system = RenderSystem(world, bus, window)
    return bus, world, ability_system, board_system, render_system

def _enter_targeting(world, bus):
    # Activate first ability of owner
    human_entities = list(world.get_component(HumanAgent))
    assert human_entities, 'No human agent found'
    owner_ent = human_entities[0][0]
    owner_comp = world.component_for_entity(owner_ent, AbilityListOwner)
    ability_entity = owner_comp.ability_entities[0]
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=ability_entity, owner_entity=owner_ent)
    targeting = list(world.get_component(TargetingState))
    assert targeting, 'Targeting state not entered'
    return owner_ent, ability_entity


def test_right_click_cancels_targeting(setup_world):
    bus, world, ability_system, board_system, render_system = setup_world
    owner_ent, ability_entity = _enter_targeting(world, bus)
    cancelled_payload = {}
    def handler(sender, **payload):
        cancelled_payload.update(payload)
    bus.subscribe(EVENT_ABILITY_TARGET_CANCELLED, handler)
    bus.emit(EVENT_MOUSE_PRESS, x=0, y=0, button=4)
    # TargetingState removed
    targeting = list(world.get_component(TargetingState))
    assert not targeting, 'Targeting state should be removed after right-click'
    assert cancelled_payload.get('ability_entity') == ability_entity
    assert cancelled_payload.get('owner_entity') == owner_ent
    assert cancelled_payload.get('reason') == 'right_click'
