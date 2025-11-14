from __future__ import annotations

from typing import Tuple

from esper import World

from ecs.components.effect import Effect
from ecs.events.bus import (
    EVENT_ABILITY_EFFECT_APPLIED,
    EVENT_BOARD_CHANGED,
    EVENT_CASCADE_COMPLETE,
    EVENT_EFFECT_APPLIED,
    EVENT_EFFECT_REFRESHED,
    EVENT_EFFECT_REMOVE,
    EVENT_MATCH_CLEARED,
    EventBus,
)
from ecs.systems.board_ops import transform_tiles_to_type, find_all_matches
from ecs.systems.turn_state_utils import get_or_create_turn_state

class BoardTransformEffectSystem:
    """Resolves board transformation effects created by abilities like tactical shift."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_EFFECT_APPLIED, self._on_effect_event)
        self.event_bus.subscribe(EVENT_EFFECT_REFRESHED, self._on_effect_event)

    def _on_effect_event(self, sender, **payload) -> None:
        if payload.get("slug") != "board_transform_type":
            return
        effect_entity = payload.get("effect_entity")
        if effect_entity is None:
            return
        try:
            effect = self.world.component_for_entity(effect_entity, Effect)
        except KeyError:
            return
        metadata = effect.metadata or {}
        target_type = metadata.get("target_type")
        if not target_type:
            self._remove_effect(effect_entity, reason="resolved")
            return
        origin_row = metadata.get("origin_row")
        origin_col = metadata.get("origin_col")
        if origin_row is None or origin_col is None:
            self._remove_effect(effect_entity, reason="resolved")
            return

        affected = transform_tiles_to_type(self.world, int(origin_row), int(origin_col), str(target_type))
        matches_present = bool(find_all_matches(self.world)) if affected else False
        ability_entity = effect.source_entity
        if ability_entity is not None:
            self.event_bus.emit(
                EVENT_ABILITY_EFFECT_APPLIED,
                ability_entity=ability_entity,
                affected=affected,
            )

        if affected:
            reason = metadata.get("reason", effect.slug)
            self.event_bus.emit(
                EVENT_BOARD_CHANGED,
                reason="ability_effect",
                positions=affected,
            )
            owner_entity = metadata.get("source_owner")
            types_payload = [(row, col, str(target_type)) for row, col in affected]
            self.event_bus.emit(
                EVENT_MATCH_CLEARED,
                positions=affected,
                types=types_payload,
                owner_entity=owner_entity,
                reason=reason,
            )

        state = get_or_create_turn_state(self.world)
        if matches_present:
            state.cascade_observed = True
        else:
            state.cascade_active = False
            state.cascade_depth = 0
            state.cascade_observed = False

        self._remove_effect(effect_entity, reason="resolved")

    def _remove_effect(self, effect_entity: int, *, reason: str) -> None:
        self.event_bus.emit(
            EVENT_EFFECT_REMOVE,
            effect_entity=effect_entity,
            reason=reason,
        )
