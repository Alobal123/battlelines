from ecs.events.bus import EventBus
from ecs.world import create_world
from ecs.utils.combatants import ensure_combatants, find_primary_opponent, set_combat_opponent
from ecs.components.combatants import Combatants
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.health import Health


def _player_and_enemy(world):
    player_entities = [entity for entity, _ in world.get_component(HumanAgent)]
    enemy_entities = [entity for entity, _ in world.get_component(RuleBasedAgent)]
    assert player_entities and enemy_entities
    return player_entities[0], enemy_entities[0]


def test_find_primary_opponent_prefers_combatants():
    bus = EventBus()
    world = create_world(bus)
    player, enemy = _player_and_enemy(world)

    assert find_primary_opponent(world, player) == enemy
    assert find_primary_opponent(world, enemy) == player


def test_set_combat_opponent_updates_component():
    bus = EventBus()
    world = create_world(bus)
    player, old_enemy = _player_and_enemy(world)

    new_enemy = world.create_entity(RuleBasedAgent(), Health(current=20, max_hp=20))
    set_combat_opponent(world, new_enemy)

    assert find_primary_opponent(world, player) == new_enemy
    assert find_primary_opponent(world, old_enemy) == player


def test_ensure_combatants_installs_component_when_missing():
    bus = EventBus()
    world = create_world(bus)
    player, enemy = _player_and_enemy(world)

    for entity, _ in world.get_component(Combatants):
        world.remove_component(entity, Combatants)
        break

    ensure_combatants(world, player, enemy)

    stored = [comp for _, comp in world.get_component(Combatants)]
    assert stored and stored[0].player_entity == player
    assert stored[0].opponent_entity == enemy
