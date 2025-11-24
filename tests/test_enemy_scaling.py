from __future__ import annotations

import random
from pathlib import Path

from esper import World

from ecs.components.health import Health
from ecs.components.story_progress_tracker import StoryProgressTracker
from ecs.events.bus import EventBus
from ecs.systems.enemy_pool_system import EnemyPoolSystem
from ecs.systems.story_progress_system import StoryProgressSystem


def _get_tracker(world: World) -> StoryProgressTracker:
    entries = list(world.get_component(StoryProgressTracker))
    assert entries, "Expected StoryProgressTracker component"
    return entries[0][1]


def test_enemy_health_scales_with_completed_locations(tmp_path) -> None:
    world = World()
    bus = EventBus()
    save_path = Path(tmp_path) / "progress.json"
    StoryProgressSystem(world, bus, save_path=save_path, load_existing=False)
    enemy_pool = EnemyPoolSystem(world, bus, rng=random.Random(4))
    world.enemy_pool = enemy_pool  # type: ignore[attr-defined]

    tracker = _get_tracker(world)
    tracker.locations_completed = 0

    base_enemy = enemy_pool.create_enemy("bloodhound")
    base_health = world.component_for_entity(base_enemy, Health)
    base_hp = base_health.max_hp

    tracker.locations_completed = 3

    scaled_enemy = enemy_pool.create_enemy("bloodhound")
    scaled_health = world.component_for_entity(scaled_enemy, Health)

    assert scaled_health.max_hp == base_hp + 15
    assert scaled_health.current == scaled_health.max_hp
