"""Test that enemies and locations are never repeated within a single game session."""
from pathlib import Path
from tempfile import TemporaryDirectory

from ecs.components.character import Character
from ecs.components.story_progress_tracker import StoryProgressTracker
from ecs.events.bus import (
    EVENT_ENEMY_DEFEATED,
    EVENT_LOCATION_ENTERED,
    EventBus,
)
from ecs.systems.enemy_pool_system import EnemyPoolSystem
from ecs.systems.story_progress_system import StoryProgressSystem
from world import create_world


def test_enemy_pool_excludes_encountered_enemies():
    """Test that EnemyPoolSystem doesn't spawn enemies that were already encountered."""
    bus = EventBus()
    world = create_world(bus)
    
    with TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "progress.json"
        progress_system = StoryProgressSystem(world, bus, save_path=save_path, load_existing=False)
        enemy_pool = EnemyPoolSystem(world, bus)
        
        # Initially all enemies should be available
        initial_available = enemy_pool._get_available_enemies()
        all_enemies = enemy_pool.known_enemy_names()
        assert len(initial_available) == len(all_enemies)
        
        # Spawn and defeat an enemy
        enemy_name = enemy_pool.random_enemy_name()
        assert enemy_name is not None
        enemy_entity = enemy_pool.create_enemy(enemy_name)
        char = world.component_for_entity(enemy_entity, Character)
        
        # Mark as defeated
        bus.emit(EVENT_ENEMY_DEFEATED, entity=enemy_entity)
        
        # Check that this enemy is now excluded
        available_after = enemy_pool._get_available_enemies()
        assert char.name not in [
            world.component_for_entity(
                enemy_pool.create_enemy(name), Character
            ).name
            for name in available_after
        ]
        assert len(available_after) == len(all_enemies) - 1
        
        # The next random enemy should never be the one we just defeated
        for _ in range(10):
            next_name = enemy_pool.random_enemy_name()
            if next_name:
                assert next_name != enemy_name, "Defeated enemy should not be spawned again"


def test_location_filtering_in_choice_window():
    """Test that spawn_location_choice_window excludes visited locations."""
    from ecs.factories.locations import spawn_location_choice_window, all_location_specs
    from ecs.components.location import LocationChoice
    
    bus = EventBus()
    world = create_world(bus)
    
    with TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "progress.json"
        progress_system = StoryProgressSystem(world, bus, save_path=save_path, load_existing=False)
        
        owner_entity = world.create_entity()
        
        # Initially all locations should be available
        all_specs = list(all_location_specs())
        
        # Skip test if there's only one location (can't test filtering)
        if len(all_specs) < 2:
            return
        
        window_entity = spawn_location_choice_window(world, owner_entity, event_bus=bus, press_id=1)
        assert window_entity is not None

        initial_choices = list(world.get_component(LocationChoice))
        assert len(initial_choices) == len(all_specs)
        initial_choice_ids = {entity for entity, _ in initial_choices}
        
        # Mark one location as visited
        visited_slug = all_specs[0].slug
        bus.emit(EVENT_LOCATION_ENTERED, location_name=visited_slug)
        
        # Spawn another choice window
        window_entity_2 = spawn_location_choice_window(world, owner_entity, event_bus=bus, press_id=2)
        assert window_entity_2 is not None
        
        # Collect only the newly generated choice entities
        refreshed_choices = [
            (entity, choice)
            for entity, choice in world.get_component(LocationChoice)
            if entity not in initial_choice_ids
        ]
        assert refreshed_choices, "Expected refreshed location choices after visiting a location"

        # Verify the visited location is not offered again
        for _, choice in refreshed_choices:
            assert choice.location_slug != visited_slug, "Visited location should not appear again"


def test_multiple_enemies_defeated_tracking():
    """Test that multiple enemy defeats are properly tracked and excluded."""
    bus = EventBus()
    world = create_world(bus)
    
    with TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "progress.json"
        progress_system = StoryProgressSystem(world, bus, save_path=save_path, load_existing=False)
        enemy_pool = EnemyPoolSystem(world, bus)
        
        all_enemies = enemy_pool.known_enemy_names()
        defeated_names = set()
        
        # Defeat all but one enemy
        for _ in range(len(all_enemies) - 1):
            available = enemy_pool._get_available_enemies()
            assert len(available) > 0, "Should have enemies remaining"
            
            enemy_name = enemy_pool.random_enemy_name()
            assert enemy_name is not None
            assert enemy_name not in defeated_names, "Should not re-spawn defeated enemy"
            
            enemy_entity = enemy_pool.create_enemy(enemy_name)
            bus.emit(EVENT_ENEMY_DEFEATED, entity=enemy_entity)
            defeated_names.add(enemy_name)
        
        # Only one enemy should remain available
        final_available = enemy_pool._get_available_enemies()
        assert len(final_available) == 1
        
        last_name = enemy_pool.random_enemy_name()
        assert last_name is not None
        assert last_name not in defeated_names
        
        # Defeat the last one
        enemy_entity = enemy_pool.create_enemy(last_name)
        bus.emit(EVENT_ENEMY_DEFEATED, entity=enemy_entity)
        
        # No enemies should be available now
        assert len(enemy_pool._get_available_enemies()) == 0
        assert enemy_pool.random_enemy_name() is None
