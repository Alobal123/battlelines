from esper import World

from ecs.components.turn_state import TurnState


def get_or_create_turn_state(world: World) -> TurnState:
    """Return the shared TurnState component, creating it if absent."""
    existing = list(world.get_component(TurnState))
    if existing:
        return existing[0][1]
    world.create_entity(TurnState())
    return list(world.get_component(TurnState))[0][1]
