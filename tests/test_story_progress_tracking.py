"""Test expanded story progress tracking (locations, enemies, dialogues, abilities)."""
from pathlib import Path
from tempfile import TemporaryDirectory

from ecs.components.character import Character
from ecs.components.story_progress_tracker import StoryProgressTracker
from ecs.events.bus import (
    EVENT_ABILITY_UNLOCKED,
    EVENT_DIALOGUE_COMPLETED,
    EVENT_ENEMY_DEFEATED,
    EVENT_LOCATION_ENTERED,
    EVENT_SKILL_GAINED,
    EventBus,
)
from ecs.systems.story_progress_system import StoryProgressSystem
from world import create_world


def test_location_tracking():
    """Test that locations visited are tracked."""
    bus = EventBus()
    world = create_world(bus)
    
    with TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "progress.json"
        system = StoryProgressSystem(world, bus, save_path=save_path, load_existing=False)
        
        # Visit some locations
        bus.emit(EVENT_LOCATION_ENTERED, location_name="Library")
        bus.emit(EVENT_LOCATION_ENTERED, location_name="Glasshouse")
        bus.emit(EVENT_LOCATION_ENTERED, location_name="Library")  # duplicate
        
        tracker: StoryProgressTracker = world.component_for_entity(
            system._tracker_entity, StoryProgressTracker
        )
        
        assert "Library" in tracker.locations_visited
        assert "Glasshouse" in tracker.locations_visited
        assert len(tracker.locations_visited) == 2  # no duplicates


def test_enemy_encounter_tracking():
    """Test that enemy names are tracked when defeated."""
    bus = EventBus()
    world = create_world(bus)
    
    with TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "progress.json"
        system = StoryProgressSystem(world, bus, save_path=save_path, load_existing=False)
        
        # Create enemies
        gardener = world.create_entity(
            Character(slug="gardener", name="Undead Gardener", description="", portrait_path="")
        )
        florist = world.create_entity(
            Character(slug="florist", name="Undead Florist", description="", portrait_path="")
        )
        
        # Defeat them
        bus.emit(EVENT_ENEMY_DEFEATED, entity=gardener)
        bus.emit(EVENT_ENEMY_DEFEATED, entity=florist)
        bus.emit(EVENT_ENEMY_DEFEATED, entity=gardener)  # defeat gardener again
        
        tracker: StoryProgressTracker = world.component_for_entity(
            system._tracker_entity, StoryProgressTracker
        )
        
        assert tracker.enemies_defeated == 3
        assert "gardener" in tracker.enemies_encountered
        assert "florist" in tracker.enemies_encountered
        assert len(tracker.enemies_encountered) == 2  # unique names only


def test_dialogue_completion_tracking():
    """Test that dialogues are tracked."""
    bus = EventBus()
    world = create_world(bus)
    
    with TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "progress.json"
        system = StoryProgressSystem(world, bus, save_path=save_path, load_existing=False)
        
        # Complete some dialogues
        bus.emit(EVENT_DIALOGUE_COMPLETED, left_entity=1, right_entity=2)
        bus.emit(EVENT_DIALOGUE_COMPLETED, left_entity=1, right_entity=3)
        bus.emit(EVENT_DIALOGUE_COMPLETED, left_entity=1, right_entity=2)  # duplicate
        
        tracker: StoryProgressTracker = world.component_for_entity(
            system._tracker_entity, StoryProgressTracker
        )
        
        assert "dialogue_1_2" in tracker.dialogues_completed
        assert "dialogue_1_3" in tracker.dialogues_completed
        assert len(tracker.dialogues_completed) == 2


def test_ability_unlocking_tracking():
    """Test that abilities unlocked are tracked in order."""
    bus = EventBus()
    world = create_world(bus)
    
    with TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "progress.json"
        system = StoryProgressSystem(world, bus, save_path=save_path, load_existing=False)
        
        # Unlock abilities
        bus.emit(EVENT_ABILITY_UNLOCKED, ability_name="Tactical Shift")
        bus.emit(EVENT_ABILITY_UNLOCKED, ability_name="Crimson Pulse")
        bus.emit(EVENT_ABILITY_UNLOCKED, ability_name="Tactical Shift")  # duplicate ignored
        
        tracker: StoryProgressTracker = world.component_for_entity(
            system._tracker_entity, StoryProgressTracker
        )
        
        assert tracker.abilities_unlocked == ["Tactical Shift", "Crimson Pulse"]


def test_skill_gained_tracking():
    """Test that skills are tracked."""
    bus = EventBus()
    world = create_world(bus)
    
    with TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "progress.json"
        system = StoryProgressSystem(world, bus, save_path=save_path, load_existing=False)
        
        # Gain skills
        bus.emit(EVENT_SKILL_GAINED, skill_name="Advanced Swapping")
        bus.emit(EVENT_SKILL_GAINED, skill_name="Combo Master")
        bus.emit(EVENT_SKILL_GAINED, skill_name="Advanced Swapping")  # duplicate
        
        tracker: StoryProgressTracker = world.component_for_entity(
            system._tracker_entity, StoryProgressTracker
        )
        
        assert "Advanced Swapping" in tracker.skills_gained
        assert "Combo Master" in tracker.skills_gained
        assert len(tracker.skills_gained) == 2


def test_progress_persistence():
    """Test that all progress data persists across load/save."""
    bus = EventBus()
    world = create_world(bus)
    
    with TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "progress.json"
        system = StoryProgressSystem(world, bus, save_path=save_path, load_existing=False)
        
        # Generate some progress
        bus.emit(EVENT_LOCATION_ENTERED, location_name="Library")
        bus.emit(EVENT_LOCATION_ENTERED, location_name="Kitchen")
        enemy = world.create_entity(
            Character(slug="scarecrow", name="Scarecrow", description="", portrait_path="")
        )
        bus.emit(EVENT_ENEMY_DEFEATED, entity=enemy)
        bus.emit(EVENT_DIALOGUE_COMPLETED, left_entity=10, right_entity=20)
        bus.emit(EVENT_ABILITY_UNLOCKED, ability_name="Test Ability")
        bus.emit(EVENT_SKILL_GAINED, skill_name="Test Skill")
        
        # Create new system instance that loads from same file
        bus2 = EventBus()
        world2 = create_world(bus2)
        system2 = StoryProgressSystem(world2, bus2, save_path=save_path, load_existing=True)
        
        tracker2: StoryProgressTracker = world2.component_for_entity(
            system2._tracker_entity, StoryProgressTracker
        )
        
        assert "Library" in tracker2.locations_visited
        assert "Kitchen" in tracker2.locations_visited
        assert "scarecrow" in tracker2.enemies_encountered
        assert tracker2.enemies_defeated == 1
        assert "dialogue_10_20" in tracker2.dialogues_completed
        assert "Test Ability" in tracker2.abilities_unlocked
        assert "Test Skill" in tracker2.skills_gained
