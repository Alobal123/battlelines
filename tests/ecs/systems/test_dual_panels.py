import pytest
from ecs.events.bus import EventBus
from world import create_world
from ecs.systems.render import RenderSystem

from tests.helpers import grant_player_abilities

class DummyWindow:
    width = 800
    height = 600

@pytest.fixture
def setup_world():
    bus = EventBus()
    world = create_world(bus)
    grant_player_abilities(world, ("tactical_shift",))
    window = DummyWindow()
    render = RenderSystem(world, bus, window)
    return bus, world, render, window


def test_second_owner_abilities_right_of_board(setup_world):
    bus, world, render, window = setup_world
    render.process()  # headless layout only
    cache = getattr(render, '_ability_layout_cache', [])
    assert cache, 'Ability layout cache empty'
    # Board extents
    from ecs.constants import GRID_COLS, TILE_SIZE
    total_width = GRID_COLS * TILE_SIZE
    board_left = (window.width - total_width) / 2
    board_right = board_left + total_width
    # Separate entries by owner
    owners = sorted({e['owner_entity'] for e in cache})
    assert len(owners) >= 2, 'Need at least two owners in cache'
    owner_to_entries = {}
    for entry in cache:
        owner_to_entries.setdefault(entry['owner_entity'], []).append(entry)
    # Pick max x for second owner and ensure it's right of board_right
    second_owner = owners[1]
    max_x_second = max(e['x'] for e in owner_to_entries[second_owner])
    assert max_x_second > board_right, 'Second owner abilities should be right of board'


def test_banks_drawn_for_all_players(setup_world):
    bus, world, render, window = setup_world
    from ecs.components.tile_bank import TileBank
    banks = list(world.get_component(TileBank))
    assert len(banks) >= 2, 'Expected at least two TileBank components (one per player)'
