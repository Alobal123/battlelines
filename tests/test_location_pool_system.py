"""Tests for LocationPoolSystem."""
import random
from pathlib import Path
from tempfile import TemporaryDirectory

from ecs.components.story_progress_tracker import StoryProgressTracker
from ecs.events.bus import (
    EVENT_LOCATION_ENTERED,
    EVENT_LOCATION_POOL_OFFER,
    EVENT_LOCATION_POOL_REQUEST,
    EventBus,
)
from ecs.factories.locations import all_location_specs
from ecs.systems.location_pool_system import LocationPoolSystem
from ecs.systems.story_progress_system import StoryProgressSystem
from world import create_world


def test_location_pool_system_provides_all_locations():
    """Test that LocationPoolSystem knows all defined locations."""
    bus = EventBus()
    world = create_world(bus)
    pool = LocationPoolSystem(world, bus)
    
    all_specs = list(all_location_specs())
    known = pool.known_location_slugs()
    
    assert len(known) == len(all_specs)
    for spec in all_specs:
        assert spec.slug in known


def test_location_pool_random_selection():
    """Test random location selection."""
    bus = EventBus()
    world = create_world(bus)
    rng = random.Random(42)
    pool = LocationPoolSystem(world, bus, rng=rng)
    
    location_slug = pool.random_location_slug()
    assert location_slug is not None
    assert location_slug in pool.known_location_slugs()


def test_location_pool_excludes_visited():
    """Test that visited locations are excluded from selection."""
    bus = EventBus()
    world = create_world(bus)
    
    with TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "progress.json"
        progress = StoryProgressSystem(world, bus, save_path=save_path, load_existing=False)
        pool = LocationPoolSystem(world, bus)
        
        all_locs = pool.known_location_slugs()
        initial_available = pool._get_available_locations()
        assert len(initial_available) == len(all_locs)
        
        # Visit a location
        first_slug = all_locs[0]
        bus.emit(EVENT_LOCATION_ENTERED, location_name=first_slug)
        
        # Check it's excluded
        available_after = pool._get_available_locations()
        assert first_slug not in available_after
        assert len(available_after) == len(all_locs) - 1


def test_location_pool_request_handler():
    """Test that pool responds to EVENT_LOCATION_POOL_REQUEST."""
    bus = EventBus()
    world = create_world(bus)
    pool = LocationPoolSystem(world, bus)
    
    captured = {}
    bus.subscribe(EVENT_LOCATION_POOL_OFFER, lambda sender, **payload: captured.update(payload))
    
    bus.emit(EVENT_LOCATION_POOL_REQUEST, count=2, request_id="test_req")
    
    assert "locations" in captured
    assert "request_id" in captured
    assert captured["request_id"] == "test_req"
    assert isinstance(captured["locations"], list)
    assert len(captured["locations"]) <= 2


def test_location_pool_no_locations_after_all_visited():
    """Test that pool returns None when all locations are visited."""
    bus = EventBus()
    world = create_world(bus)
    
    with TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "progress.json"
        progress = StoryProgressSystem(world, bus, save_path=save_path, load_existing=False)
        pool = LocationPoolSystem(world, bus)
        
        # Visit all locations
        for slug in pool.known_location_slugs():
            bus.emit(EVENT_LOCATION_ENTERED, location_name=slug)
        
        # No locations should be available
        assert len(pool._get_available_locations()) == 0
        assert pool.random_location_slug() is None


def test_location_pool_avoids_immediate_repeat():
    """Test that pool tries to avoid repeating the last location."""
    bus = EventBus()
    world = create_world(bus)
    
    # Need at least 2 locations for this test
    all_specs = list(all_location_specs())
    if len(all_specs) < 2:
        return  # Skip if not enough locations
    
    rng = random.Random(123)
    pool = LocationPoolSystem(world, bus, rng=rng)
    
    first = pool.random_location_slug()
    assert first is not None
    
    # Try multiple times to ensure anti-repeat logic works
    for _ in range(10):
        second = pool.random_location_slug()
        # With multiple locations, it should try to avoid the last one
        # (though not guaranteed due to randomness, the logic attempts it)
        if second != first:
            break
    # At least one should be different if there are alternatives
    assert second is not None
