import pytest
from ecs.events.bus import EventBus, EVENT_ABILITY_ACTIVATE_REQUEST
from ecs.world import create_world
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.ability_targeting_system import AbilityTargetingSystem
from ecs.systems.render import RenderSystem
from ecs.systems.input import InputSystem
from ecs.components.ability_list_owner import AbilityListOwner

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
    ability_system = AbilitySystem(world, bus)
    input_system = InputSystem(bus, window, world)
    return bus, world, render, ability_system, input_system


def test_each_owner_has_independent_ability_instances(setup_world):
    bus, world, render, ability_system, input_system = setup_world
    owners = list(world.get_component(AbilityListOwner))
    assert len(owners) >= 2, 'World should have at least two owners'
    # Collect ability entities per owner
    owner_data = []
    for ent, comp in owners:
        owner_data.append((ent, set(comp.ability_entities)))
    # Ensure no sharing of the same ability entity id between owners
    sets = [s for _, s in owner_data]
    intersection = sets[0].intersection(*sets[1:]) if len(sets) > 1 else set()
    assert not intersection, 'Ability entities must be unique per owner'


def test_layout_entries_include_owner(setup_world):
    bus, world, render, *_ = setup_world
    render.process()  # headless layout build
    cache = getattr(render, '_ability_layout_cache', [])
    assert cache, 'Ability layout cache should not be empty'
    owner_entities = {entry.get('owner_entity') for entry in cache}
    assert len(owner_entities) >= 2, 'Layout should contain entries for both owners'

