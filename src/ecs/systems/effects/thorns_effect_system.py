from __future__ import annotations

from esper import World

from ecs.components.effect import Effect
from ecs.components.effect_list import EffectList
from ecs.events.bus import EVENT_EFFECT_APPLY, EVENT_HEALTH_DAMAGE, EventBus


class ThornsEffectSystem:
    """Reflect damage to attackers when a thorned owner is struck."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_HEALTH_DAMAGE, self._on_health_damage)

    def _on_health_damage(self, sender, **payload) -> None:
        target = payload.get("target_entity")
        if target is None:
            return
        attacker = payload.get("source_owner")
        if attacker is None or attacker == target:
            return
        if payload.get("reason") == "thorns":
            return
        if not self._has_thorns(target):
            return
        if not self._is_reflectable(payload):
            return
        damage = self._thorns_damage(target)
        if damage <= 0:
            return
        self.event_bus.emit(
            EVENT_EFFECT_APPLY,
            owner_entity=attacker,
            source_entity=None,
            slug="damage",
            turns=0,
            metadata={
                "amount": damage,
                "reason": "thorns",
                "source_owner": target,
            },
        )

    def _has_thorns(self, owner: int) -> bool:
        effect_list = self._effect_list(owner)
        if effect_list is None:
            return False
        for effect_id in list(effect_list.effect_entities):
            effect = self._effect(effect_id)
            if effect is None:
                continue
            if effect.slug == "thorns":
                return True
        return False

    def _thorns_damage(self, owner: int) -> int:
        effect_list = self._effect_list(owner)
        if effect_list is None:
            return 0
        total = 0
        for effect_id in list(effect_list.effect_entities):
            effect = self._effect(effect_id)
            if effect is None or effect.slug != "thorns":
                continue
            total += self._coerce_positive(effect.metadata.get("amount"), default=1)
        return total

    def _is_reflectable(self, payload: dict) -> bool:
        effect_entity = payload.get("effect_entity")
        reason = payload.get("reason")
        if effect_entity is None:
            return reason == "witchfire"
        effect = self._effect(effect_entity)
        if effect is None:
            return reason == "witchfire"
        if effect.slug != "damage":
            return reason == "witchfire"
        if effect.source_entity is not None:
            return True
        return reason == "witchfire"

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
    def _coerce_positive(value, *, default: int = 0) -> int:
        try:
            amount = int(value)
        except (TypeError, ValueError):
            return default
        return amount if amount > 0 else default