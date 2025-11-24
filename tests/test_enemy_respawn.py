import random
from typing import cast

from ecs.events.bus import EventBus, EVENT_ENTITY_DEFEATED
from world import create_world
from ecs.systems.defeat_system import DefeatSystem
from ecs.components.active_turn import ActiveTurn
from ecs.components.character import Character
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.turn_order import TurnOrder


def _single_entity(world, component_type):
    entries = list(world.get_component(component_type))
    assert len(entries) == 1
    return entries[0][0]


def _single_component(world, component_type):
    entries = list(world.get_component(component_type))
    assert len(entries) == 1
    return entries[0][1]


def test_enemy_respawn_uses_pool_and_resets_turn_order():
    event_bus = EventBus()
    world = create_world(event_bus, randomize_enemy=True)
    DefeatSystem(world, event_bus)

    enemy_pool = getattr(world, "enemy_pool")
    enemy_pool._rng = random.Random(1)

    human = _single_entity(world, HumanAgent)
    first_enemy = _single_entity(world, RuleBasedAgent)
    first_slug = world.component_for_entity(first_enemy, Character).slug

    event_bus.emit(EVENT_ENTITY_DEFEATED, entity=first_enemy)

    second_enemy = _single_entity(world, RuleBasedAgent)
    second_slug = world.component_for_entity(second_enemy, Character).slug
    assert second_enemy != first_enemy
    assert second_slug in set(enemy_pool.known_enemy_names())

    turn_order = cast(TurnOrder, _single_component(world, TurnOrder))
    assert list(turn_order.owners) == [human, second_enemy]
    active_turn = cast(ActiveTurn, _single_component(world, ActiveTurn))
    assert active_turn.owner_entity == human

    event_bus.emit(EVENT_ENTITY_DEFEATED, entity=second_enemy)

    third_enemy = _single_entity(world, RuleBasedAgent)
    third_slug = world.component_for_entity(third_enemy, Character).slug
    assert third_enemy not in {first_enemy, second_enemy}
    assert third_slug in set(enemy_pool.known_enemy_names())
