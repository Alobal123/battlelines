"""Integration test showing LocationPoolSystem usage with MatchSetupSystem."""
from ecs.events.bus import (
    EVENT_LOCATION_POOL_OFFER,
    EVENT_LOCATION_POOL_REQUEST,
    EventBus,
)
from ecs.systems.location_pool_system import LocationPoolSystem
from world import create_world


def test_location_pool_integration_with_world():
    """Test that LocationPoolSystem is accessible via world attribute."""
    bus = EventBus()
    world = create_world(bus)
    
    # LocationPoolSystem should be accessible via world
    assert hasattr(world, "location_pool")
    location_pool = getattr(world, "location_pool")
    assert isinstance(location_pool, LocationPoolSystem)
    
    # It should know about locations
    locations = location_pool.known_location_slugs()
    assert len(locations) > 0


def test_location_pool_request_response_flow():
    """Test the request/offer event flow."""
    bus = EventBus()
    world = create_world(bus)
    
    captured_offers = []
    
    def on_offer(sender, **payload):
        captured_offers.append(payload)
    
    bus.subscribe(EVENT_LOCATION_POOL_OFFER, on_offer)
    
    # Request 3 locations
    bus.emit(EVENT_LOCATION_POOL_REQUEST, count=3, request_id="test_123")
    
    # Should receive an offer
    assert len(captured_offers) == 1
    offer = captured_offers[0]
    assert offer["request_id"] == "test_123"
    assert "locations" in offer
    assert isinstance(offer["locations"], list)
    # Should offer up to 3 (or all available if fewer)
    assert len(offer["locations"]) <= 3


def test_location_pool_with_match_setup_pattern():
    """Test location pool usage pattern similar to how MatchSetupSystem would use it."""
    bus = EventBus()
    world = create_world(bus)
    location_pool = getattr(world, "location_pool")
    
    # Pattern: Get a random location for a match
    location_slug = location_pool.random_location_slug()
    assert location_slug is not None
    
    # Pattern: Get multiple location options for player choice
    available = location_pool._get_available_locations()
    assert len(available) > 0
    
    # All available should be valid location slugs
    known = location_pool.known_location_slugs()
    for slug in available:
        assert slug in known
