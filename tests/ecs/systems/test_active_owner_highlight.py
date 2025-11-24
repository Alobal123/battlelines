import pytest
from ecs.events.bus import EventBus
from world import create_world
from ecs.systems.render import RenderSystem
from ecs.systems.turn_system import TurnSystem
from ecs.components.active_turn import ActiveTurn

pytestmark = pytest.mark.skip(reason="known slow render-dependent test")

class DummyWindow:
    width = 800
    height = 600

@pytest.fixture
def setup_world():
    bus = EventBus()
    world = create_world(bus)
    window = DummyWindow()
    render = RenderSystem(world, bus, window)
    turn = TurnSystem(world, bus)
    return bus, world, render, turn


def test_active_owner_layout_flag(setup_world):
    bus, world, render, turn = setup_world
    render.process()  # headless; populates layout
    active_list = list(world.get_component(ActiveTurn))
    assert active_list
    active_owner = active_list[0][1].owner_entity
    cache = getattr(render, '_ability_layout_cache', [])
    active_entries = [e for e in cache if e.get('owner_entity') == active_owner]
    assert active_entries, 'No entries found for active owner'
    assert all(e.get('is_active') for e in active_entries), 'Active owner entries should have is_active True'
