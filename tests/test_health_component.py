from ecs.events.bus import EventBus
from ecs.world import create_world, initialize_combat_entities
from ecs.components.game_state import GameMode
from ecs.components.health import Health


def test_players_have_health():
    bus = EventBus()
    world = create_world(bus, initial_mode=GameMode.COMBAT)
    initialize_combat_entities(world)
    health_components = list(world.get_component(Health))
    assert len(health_components) >= 2, 'Expected at least two Health components (two players)'
    for _, hp in health_components:
        assert hp.max_hp == 30
        assert hp.current == 30
        assert hp.is_alive()
        hp.current = -5
        hp.clamp()
        assert hp.current == 0
        hp.current = 999
        hp.clamp()
        assert hp.current == 30
