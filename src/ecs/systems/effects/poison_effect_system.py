from __future__ import annotations

from esper import World

from ecs.components.effect import Effect
from ecs.components.effect_list import EffectList
from ecs.events.bus import EVENT_TURN_ADVANCED, EVENT_HEALTH_DAMAGE, EventBus


class PoisonEffectSystem:
    """Applies poison damage at the start of the affected entity's turn."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_TURN_ADVANCED, self._on_turn_advanced)

    def _on_turn_advanced(self, sender, **payload) -> None:
        owner = payload.get("new_owner")
        if owner is None:
            return
        effect_list = self._effect_list(owner)
        if effect_list is None:
            return
        for effect_entity in list(effect_list.effect_entities):
            effect = self._effect(effect_entity)
            if effect is None or effect.slug != "poison":
                continue
            amount = self._coerce_amount(effect.metadata.get("amount"))
            if amount <= 0:
                continue
            reason = str(effect.metadata.get("reason", "poison"))
            self.event_bus.emit(
                EVENT_HEALTH_DAMAGE,
                source_owner=None,
                target_entity=owner,
                amount=amount,
                reason=reason,
                effect_entity=effect_entity,
                effect_slug="poison",
            )

    def _effect_list(self, owner: int) -> EffectList | None:
        try:
            return self.world.component_for_entity(owner, EffectList)
        except KeyError:
            return None

    def _effect(self, entity: int) -> Effect | None:
        try:
            return self.world.component_for_entity(entity, Effect)
        except KeyError:
            return None

    @staticmethod
    def _coerce_amount(value) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0
