from ecs.events.bus import EventBus, EVENT_TILE_CLICK, EVENT_TILE_SWAP_REQUEST, EVENT_TICK
from world import create_world
from ecs.systems.board import BoardSystem
from ecs.systems.render import RenderSystem
from ecs.systems.animation import AnimationSystem
from ecs.systems.match import MatchSystem
from ecs.systems.match_resolution import MatchResolutionSystem
from ecs.systems.turn_system import TurnSystem

class DummyWindow:
    def __init__(self):
        self.width = 800
        self.height = 600


def drive_ticks(bus, n=5):
    for _ in range(n):
        bus.emit(EVENT_TICK, dt=0.02)


def test_selection_clears_on_swap_request():
    bus = EventBus(); world = create_world(bus); window = DummyWindow()
    board = BoardSystem(world, bus, 3, 3)
    MatchSystem(world, bus)
    AnimationSystem(world, bus)
    render = RenderSystem(world, bus, window)
    TurnSystem(world, bus)
    MatchResolutionSystem(world, bus)
    # Click two adjacent tiles to initiate swap
    bus.emit(EVENT_TILE_CLICK, row=0, col=0)
    assert render.selected == (0,0)
    bus.emit(EVENT_TILE_CLICK, row=0, col=1)  # second click triggers swap request
    # After swap request selection should clear immediately
    assert render.selected is None
