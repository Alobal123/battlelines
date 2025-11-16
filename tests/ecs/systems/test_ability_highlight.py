import pytest
from ecs.events.bus import EventBus, EVENT_ABILITY_ACTIVATE_REQUEST
from ecs.world import create_world
from ecs.systems.render import RenderSystem
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.ability_targeting_system import AbilityTargetingSystem
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.human_agent import HumanAgent

class DummyWindow:
    width = 800
    height = 600

@pytest.fixture
def setup_world():
    bus = EventBus()
    world = create_world(bus)
    window = DummyWindow()
    render = RenderSystem(world, bus, window)
    AbilityTargetingSystem(world, bus)
    ability = AbilitySystem(world, bus)
    return bus, world, render, ability


def test_ability_highlight_flag(setup_world):
    bus, world, render, ability_system = setup_world
    human_entities = list(world.get_component(HumanAgent))
    assert human_entities, 'No human agent found'
    owner_ent = human_entities[0][0]
    owner_comp = world.component_for_entity(owner_ent, AbilityListOwner)
    ability_entity = owner_comp.ability_entities[0]
    # Activate ability (enter targeting)
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=ability_entity, owner_entity=owner_ent)
    # Run a render pass to populate layout cache
    render.process()
    # Find layout entry
    cache = getattr(render, '_ability_layout_cache', [])
    entry = next((e for e in cache if e['entity'] == ability_entity), None)
    assert entry is not None, 'Ability layout entry not found'
    assert entry.get('is_targeting') is True, 'Activated ability should have is_targeting True'
