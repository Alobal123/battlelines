from __future__ import annotations

from esper import World

from ecs.components.effect import Effect
from ecs.components.effect_list import EffectList
from ecs.events.bus import EVENT_TURN_ADVANCED, EVENT_HEALTH_DAMAGE, EVENT_EFFECT_REMOVE, EventBus


class PoisonEffectSystem:
    """Applies poison damage at the start of the affected entity's turn, consuming one stack."""

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
            count = max(0, int(getattr(effect, "count", 0)))
            if count <= 0:
                self._remove_effect(effect_entity)
                continue
            damage = self._calculate_damage(effect, count)
            reason = str(effect.metadata.get("reason", "poison"))
            self.event_bus.emit(
                EVENT_HEALTH_DAMAGE,
                source_owner=None,
                target_entity=owner,
                amount=damage,
                reason=reason,
                effect_entity=effect_entity,
                effect_slug="poison",
            )
            effect.count = max(0, count - 1)
            if effect.count <= 0:
                self._remove_effect(effect_entity)

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

    def _calculate_damage(self, effect: Effect, count: int) -> int:
        base = self._coerce_amount(effect.metadata.get("damage_per_tick", 1))
        if base <= 0:
            base = 1
        bonus = count // 5
        return base + bonus

    def _remove_effect(self, effect_entity: int) -> None:
        self.event_bus.emit(
            EVENT_EFFECT_REMOVE,
            effect_entity=effect_entity,
            reason="poison_depleted",
        )
