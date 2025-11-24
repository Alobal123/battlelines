from ecs.events.bus import EventBus
from world import create_world, initialize_combat_entities
from ecs.components.game_state import GameMode
from ecs.components.health import Health
from ecs.components.human_agent import HumanAgent


def test_players_have_health():
    bus = EventBus()
    world = create_world(bus, initial_mode=GameMode.COMBAT)
    initialize_combat_entities(world)
    health_components = list(world.get_component(Health))
    assert len(health_components) >= 2, 'Expected at least two Health components (two players)'
    human_entities = {entity for entity, _ in world.get_component(HumanAgent)}
    assert human_entities, "Expected at least one human-controlled entity"

    for entity, hp in health_components:
        if entity not in human_entities:
            continue
        max_hp = hp.max_hp
        assert hp.current == max_hp
        assert hp.is_alive()
        hp.current = -5
        hp.clamp()
        assert hp.current == 0
        hp.current = max_hp + 999
        hp.clamp()
        assert hp.current == max_hp
