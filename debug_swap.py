import sys, os
ROOT = os.path.dirname(__file__)
SRC = os.path.join(ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)
from ecs.events.bus import EventBus
from ecs.events.bus import EVENT_TILE_SWAP_REQUEST, EVENT_TICK, EVENT_TILE_SWAP_FINALIZE, EVENT_TILE_SWAP_DO, EVENT_MATCH_FOUND
from ecs.systems.board import BoardSystem
from ecs.systems.render import RenderSystem
from ecs.systems.match import MatchSystem
from ecs.systems.match_resolution import MatchResolutionSystem
from ecs.world import create_world
from ecs.components.tile import TileColor

class DummyWindow:
    def __init__(self):
        self.width=800; self.height=600

def drive(bus, ticks):
    for _ in range(ticks):
        bus.emit(EVENT_TICK, dt=0.02)

bus=EventBus()
world=create_world(bus)
window=DummyWindow()
board=BoardSystem(world,bus,5,5)
MatchSystem(world,bus)
RenderSystem(world,bus,window)
MatchResolutionSystem(world,bus,rows=5,cols=5)

# setup colors for horizontal match after swap (2,2)<->(2,3)
for c in range(0,4):
    ent=board._get_entity_at(2,c)
    col=(10,10,10) if c!=2 else (20,20,20)
    world.component_for_entity(ent, TileColor).color=col

received=[]
for ev in [EVENT_TILE_SWAP_REQUEST, EVENT_TILE_SWAP_DO, EVENT_TILE_SWAP_FINALIZE, EVENT_MATCH_FOUND]:
    bus.subscribe(ev, lambda s, _ev=ev, **k: received.append(_ev))

bus.emit(EVENT_TILE_SWAP_REQUEST, src=(2,2), dst=(2,3))
from ecs.systems.render import RenderSystem
# Need access to render system instance; reconstruct or store earlier reference

# Reinitialize for clarity
bus=EventBus(); world=create_world(bus); window=DummyWindow(); board=BoardSystem(world,bus,5,5); MatchSystem(world,bus); render=RenderSystem(world,bus,window); MatchResolutionSystem(world,bus,rows=5,cols=5)
for c in range(0,4):
    ent=board._get_entity_at(2,c)
    col=(10,10,10) if c!=2 else (20,20,20)
    world.component_for_entity(ent, TileColor).color=col
received=[]
for ev in [EVENT_TILE_SWAP_REQUEST, EVENT_TILE_SWAP_DO, EVENT_TILE_SWAP_FINALIZE, EVENT_MATCH_FOUND]:
    bus.subscribe(ev, lambda s, _ev=ev, **k: received.append(_ev))
bus.emit(EVENT_TILE_SWAP_REQUEST, src=(2,2), dst=(2,3))
print('after request active_swap=', render.active_swap, 'phase', render.swap_phase, 'pending', render.pending_swap_valid)
drive(bus,15)
print('after 15 ticks active_swap=', render.active_swap, 'phase', render.swap_phase, 'pending', render.pending_swap_valid, 'events', received)
drive(bus,15)
print('after 30 ticks active_swap=', render.active_swap, 'phase', render.swap_phase, 'pending', render.pending_swap_valid, 'events', received)

drive(bus,15)
print('after 15 ticks events', received)

drive(bus,15)
print('after 30 ticks events', received)
