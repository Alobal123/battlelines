from __future__ import annotations

from esper import World

from ecs.components.effect import Effect
from ecs.components.effect_list import EffectList
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
        bonus = self._damage_bonus(effect.metadata.get("source_owner"))
        if bonus:
            amount += bonus
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

    def _damage_bonus(self, owner_entity) -> int:
        if owner_entity is None:
            return 0
        try:
            effect_list: EffectList = self.world.component_for_entity(owner_entity, EffectList)
        except KeyError:
            return 0
        bonus = 0
        for effect_id in list(effect_list.effect_entities):
            try:
                active_effect: Effect = self.world.component_for_entity(effect_id, Effect)
            except KeyError:
                continue
            if active_effect.slug != "damage_bonus":
                continue
            bonus += self._coerce_int(active_effect.metadata.get("bonus"))
        return bonus
