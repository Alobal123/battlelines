from __future__ import annotations

from esper import World

from ecs.components.effect import Effect
from ecs.events.bus import (
    EVENT_EFFECT_APPLIED,
    EVENT_EFFECT_REFRESHED,
    EVENT_EFFECT_REMOVE,
    EVENT_HEALTH_DAMAGE,
    EventBus,
)


class DamageEffectSystem:
    """Handles immediate damage effects when they are applied."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_EFFECT_APPLIED, self._on_effect_event)
        self.event_bus.subscribe(EVENT_EFFECT_REFRESHED, self._on_effect_event)

    def _on_effect_event(self, sender, **payload) -> None:
        if payload.get("slug") != "damage":
            return
        effect_entity = payload.get("effect_entity")
        if effect_entity is None:
            return
        try:
            effect = self.world.component_for_entity(effect_entity, Effect)
        except KeyError:
            return
        amount = self._coerce_int(effect.metadata.get("amount"))
        if amount <= 0:
            self._remove_effect(effect_entity, reason="resolved")
            return
        target = effect.owner_entity
        if target is None:
            self._remove_effect(effect_entity, reason="resolved")
            return
        reason = str(effect.metadata.get("reason", "damage"))
        source_owner = effect.metadata.get("source_owner")
        self.event_bus.emit(
            EVENT_HEALTH_DAMAGE,
            source_owner=source_owner,
            target_entity=target,
            amount=amount,
            reason=reason,
            effect_entity=effect_entity,
        )
        self._remove_effect(effect_entity, reason="resolved")

    def _remove_effect(self, effect_entity: int, *, reason: str) -> None:
        self.event_bus.emit(
            EVENT_EFFECT_REMOVE,
            effect_entity=effect_entity,
            reason=reason,
        )

    @staticmethod
    def _coerce_int(value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
