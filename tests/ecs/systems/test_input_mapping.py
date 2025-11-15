import pytest
from ecs.events.bus import EventBus, EVENT_MOUSE_PRESS
from ecs.world import create_world
from ecs.systems.board import BoardSystem
from ecs.systems.render import RenderSystem
from ecs.systems.input import InputSystem
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.ability_targeting_system import AbilityTargetingSystem
from ecs.systems.turn_system import TurnSystem
from ecs.systems.tile_bank_system import TileBankSystem
from ecs.systems.match import MatchSystem
from ecs.systems.match_resolution import MatchResolutionSystem
from ecs.components.targeting_state import TargetingState
from ecs.components.active_turn import ActiveTurn
from ecs.events.bus import EVENT_TILE_CLICK
from ecs.components.human_agent import HumanAgent

@pytest.fixture
def setup_world():
    bus = EventBus(); world = create_world(bus)
    board = BoardSystem(world, bus)
    match = MatchSystem(world, bus)
    render = RenderSystem(world, bus, window=type('W', (), {'width': 1920, 'height': 1080})())
    # Attach render_system reference to window to enable dynamic geometry path in InputSystem
    setattr(render.window, 'render_system', render)
    match_res = MatchResolutionSystem(world, bus)
    tile_bank = TileBankSystem(world, bus)
    AbilityTargetingSystem(world, bus)
    ability = AbilitySystem(world, bus)
    turn = TurnSystem(world, bus)
    input_sys = InputSystem(bus, render.window, world)
    active_turn_entries = list(world.get_component(ActiveTurn))
    if active_turn_entries:
        _, active_turn = active_turn_entries[0]
        human_owner = next((ent for ent, _ in world.get_component(HumanAgent)), None)
        if human_owner is not None:
            active_turn.owner_entity = human_owner
    return bus, world, board, render, input_sys

# Utility: capture emitted tile clicks
class ClickCapture:
    def __init__(self, bus: EventBus):
        self.received = []
        bus.subscribe(EVENT_TILE_CLICK, self.on_click)
    def on_click(self, sender, **payload):
        self.received.append((payload.get('row'), payload.get('col')))


def test_click_center_first_tile_maps_correctly(setup_world):
    bus, world, board, render, input_sys = setup_world
    # Simulate dynamic scaling calculation
    render.notify_resize(render.window.width, render.window.height)
    from ecs.ui.layout import compute_board_geometry
    tile_size, start_x, start_y = compute_board_geometry(render.window.width, render.window.height)
    cap = ClickCapture(bus)
    # Click center of tile (0,0)
    click_x = start_x + tile_size/2
    click_y = start_y + tile_size/2
    bus.emit(EVENT_MOUSE_PRESS, x=click_x, y=click_y, button=1)
    assert cap.received == [(0,0)], f"Expected click mapped to (0,0) got {cap.received}"


def test_click_outside_board_no_event(setup_world):
    bus, world, board, render, input_sys = setup_world
    render.notify_resize(render.window.width, render.window.height)
    from ecs.ui.layout import compute_board_geometry
    tile_size, start_x, start_y = compute_board_geometry(render.window.width, render.window.height)
    cap = ClickCapture(bus)
    # Outside to left
    bus.emit(EVENT_MOUSE_PRESS, x=start_x - 10, y=start_y + tile_size/2, button=1)
    assert cap.received == []
