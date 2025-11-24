from __future__ import annotations

from typing import Any

from esper import World

from ecs.components.location import CurrentLocation, LocationChoice
from ecs.events.bus import (
    EVENT_CHOICE_SELECTED,
    EVENT_LOCATION_CHOICE_GRANTED,
    EVENT_LOCATION_ENTERED,
    EventBus,
)
from ecs.factories.locations import get_location_spec


class LocationChoiceSystem:
    """Handles location selection via the generic choice window."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_CHOICE_SELECTED, self._on_choice_selected)

    def _on_choice_selected(self, sender: Any, **payload: Any) -> None:
        choice_entity = payload.get("choice_entity")
        if choice_entity is None:
            return
        try:
            choice = self.world.component_for_entity(choice_entity, LocationChoice)
        except KeyError:
            return
        spec = get_location_spec(choice.location_slug)
        if spec is None:
            return
        current_location = CurrentLocation(
            slug=spec.slug,
            name=spec.name,
            description=spec.description,
            enemy_names=tuple(spec.enemy_names),
        )
        try:
            self.world.add_component(choice.owner_entity, current_location)
        except ValueError:
            try:
                self.world.remove_component(choice.owner_entity, CurrentLocation)
            except (KeyError, ValueError):
                pass
            self.world.add_component(choice.owner_entity, current_location)
        
        # Emit location entered for story tracking
        self.event_bus.emit(EVENT_LOCATION_ENTERED, location_name=spec.slug)
        
        self.event_bus.emit(
            EVENT_LOCATION_CHOICE_GRANTED,
            owner_entity=choice.owner_entity,
            location_slug=spec.slug,
            location_name=spec.name,
            choice_entity=choice_entity,
            window_entity=payload.get("window_entity"),
            press_id=payload.get("press_id"),
        )
