import sys, os
ROOT=os.path.dirname(__file__); SRC=os.path.join(ROOT,'src');
if SRC not in sys.path: sys.path.insert(0,SRC)
from ecs.events.bus import EventBus, EVENT_TILE_SWAP_REQUEST
from ecs.world import create_world
from ecs.systems.match import MatchSystem
from ecs.systems.render import RenderSystem
from ecs.systems.board import BoardSystem

class DummyWindow: width=800; height=600

bus=EventBus(); world=create_world(bus)
BoardSystem(world,bus,5,5)
MatchSystem(world,bus)
print('Signals after MatchSystem init', bus._signals.keys(), 'receivers', bus._signals[EVENT_TILE_SWAP_REQUEST].receivers)
RenderSystem(world,bus, DummyWindow())
print('Signals after RenderSystem init', bus._signals.keys(), 'receivers', bus._signals[EVENT_TILE_SWAP_REQUEST].receivers)
