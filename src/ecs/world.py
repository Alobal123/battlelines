from esper import World
from .events.bus import EventBus

def create_world(event_bus: EventBus) -> World:
    world = World()
    # Future: register systems dynamically based on config
    return world
