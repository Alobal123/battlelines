"""Location pool system for selecting encounter locations."""
from __future__ import annotations

import random
from typing import Sequence

from esper import World

from ecs.components.story_progress_tracker import StoryProgressTracker
from ecs.events.bus import (
    EVENT_LOCATION_POOL_OFFER,
    EVENT_LOCATION_POOL_REQUEST,
    EventBus,
)
from ecs.factories.locations import all_location_specs


class LocationPoolSystem:
    """Provides location selection capabilities for match setup."""

    def __init__(self, world: World, event_bus: EventBus, *, rng: random.Random | None = None) -> None:
        self.world = world
        self.event_bus = event_bus
        candidate_rng = rng or getattr(world, "random", None)
        self._rng: random.Random = candidate_rng or random.SystemRandom()
        self._locations: Sequence[str] = tuple(spec.slug for spec in all_location_specs())
        self._last_location_slug: str | None = None
        self.event_bus.subscribe(EVENT_LOCATION_POOL_REQUEST, self._on_request)

    def known_location_slugs(self) -> Sequence[str]:
        """Return all known location slugs."""
        return self._locations

    def _get_available_locations(self) -> Sequence[str]:
        """Return location slugs that haven't been visited yet in this game."""
        tracker_entries = list(self.world.get_component(StoryProgressTracker))
        if not tracker_entries:
            return self._locations
        _, tracker = tracker_entries[0]
        return tuple(slug for slug in self._locations if slug not in tracker.locations_visited)

    def random_location_slug(self) -> str | None:
        """Select a random unvisited location, avoiding consecutive repeats when possible."""
        available = self._get_available_locations()
        if not available:
            return None
        if len(available) == 1:
            choice = available[0]
        else:
            choice = self._rng.choice(available)
            if choice == self._last_location_slug:
                # Try to avoid repeating the same location consecutively when alternatives exist.
                for _ in range(len(available) - 1):
                    new_choice = self._rng.choice(available)
                    if new_choice != self._last_location_slug:
                        choice = new_choice
                        break
                else:
                    # Deterministic fallback to the next available slug.
                    for candidate in available:
                        if candidate != self._last_location_slug:
                            choice = candidate
                            break
        self._last_location_slug = choice
        return choice

    def _on_request(self, sender, **payload) -> None:
        """Handle location pool requests by offering available locations."""
        count = payload.get("count", 1)
        request_id = payload.get("request_id")
        try:
            count_int = int(count)
        except (TypeError, ValueError):
            return
        if count_int <= 0:
            return
        available = self._get_available_locations()
        choices = list(available)
        self._rng.shuffle(choices)
        offers = choices[:count_int]
        self.event_bus.emit(
            EVENT_LOCATION_POOL_OFFER,
            locations=offers,
            request_id=request_id,
        )
