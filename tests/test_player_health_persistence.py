"""Tests ensuring player health persists across encounters within a location."""
from pathlib import Path
from tempfile import TemporaryDirectory

from ecs.components.health import Health
from ecs.components.forbidden_knowledge import ForbiddenKnowledge
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.events.bus import EventBus, EVENT_ENTITY_DEFEATED, EVENT_LOCATION_ENTERED
from ecs.systems.defeat_system import DefeatSystem
from ecs.systems.story_progress_system import StoryProgressSystem
from world import create_world


def _current_enemy(world):
    enemies = list(world.get_component(RuleBasedAgent))
    assert enemies, "Expected an enemy to be present"
    return enemies[0][0]


def _player_health(world):
    players = list(world.get_component(HumanAgent))
    assert players, "Expected a human-controlled player"
    player_entity = players[0][0]
    return world.component_for_entity(player_entity, Health)


def test_player_health_persists_until_location_complete():
    bus = EventBus()
    world = create_world(bus, randomize_enemy=True)

    with TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "progress.json"
        StoryProgressSystem(world, bus, save_path=save_path, load_existing=False)
        DefeatSystem(world, bus)

        health = _player_health(world)
        max_hp = health.max_hp
        damage = min(25, max_hp - 1) if max_hp > 0 else 0
        damaged_hp = max(1, max_hp - damage) if max_hp > 1 else max_hp
        health.current = damaged_hp  # Damage Fiora prior to the first encounter

        meter_entries = list(world.get_component(ForbiddenKnowledge))
        meter_value = None
        if meter_entries:
            _, meter = meter_entries[0]
            meter_value = min(max(meter.max_value // 2, 1), meter.max_value - 1)
            meter.value = meter_value
            meter.chaos_released = False

        bus.emit(EVENT_LOCATION_ENTERED, location_name="arcane_library")

        # Defeat two enemies within the same location; health should remain damaged.
        for _ in range(2):
            enemy_entity = _current_enemy(world)
            bus.emit(EVENT_ENTITY_DEFEATED, entity=enemy_entity)
            assert health.current == damaged_hp
            if meter_value is not None:
                meter_entries = list(world.get_component(ForbiddenKnowledge))
                _, meter = meter_entries[0]
                assert meter.value == meter_value

        # Defeating the third enemy completes the location and should restore health.
        enemy_entity = _current_enemy(world)
        bus.emit(EVENT_ENTITY_DEFEATED, entity=enemy_entity)
        assert health.current == max_hp
        if meter_value is not None:
            meter_entries = list(world.get_component(ForbiddenKnowledge))
            _, meter = meter_entries[0]
            assert meter.value == 0
            assert meter.chaos_released is False
