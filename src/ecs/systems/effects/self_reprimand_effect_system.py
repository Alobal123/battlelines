from __future__ import annotations

from esper import World

from ecs.components.effect import Effect
from ecs.components.effect_list import EffectList
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.events.bus import (
    EVENT_EFFECT_APPLY,
    EVENT_HEALTH_DAMAGE,
    EVENT_BANK_MANA,
    EventBus,
)


class SelfReprimandEffectSystem:
    """Applies retaliation damage and mana when owners hurt themselves."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_HEALTH_DAMAGE, self._on_health_damage)

    def _on_health_damage(self, sender, **payload) -> None:
        owner = payload.get("source_owner")
        target = payload.get("target_entity")
        amount = self._coerce_positive(payload.get("amount"))
        if owner is None or target is None:
            return
        if owner != target or amount <= 0:
            return
        aggregates = self._aggregate_effects(int(owner))
        if aggregates is None:
            return
        bonus_damage, mana_amount, mana_type, reason = aggregates
        if bonus_damage > 0:
            opponent = self._find_opponent(int(owner))
            if opponent is not None:
                self.event_bus.emit(
                    EVENT_EFFECT_APPLY,
                    owner_entity=opponent,
                    source_entity=None,
                    slug="damage",
                    turns=0,
                    metadata={
                        "amount": bonus_damage,
                        "reason": reason,
                        "source_owner": owner,
                    },
                )
        if mana_amount > 0 and mana_type:
            self.event_bus.emit(
                EVENT_BANK_MANA,
                owner_entity=owner,
                type_name=mana_type,
                amount=mana_amount,
                source="self_reprimand",
            )

    def _aggregate_effects(self, owner: int) -> tuple[int, int, str, str] | None:
        effect_list = self._effect_list(owner)
        if effect_list is None:
            return None
        bonus_damage = 0
        mana_amount = 0
        mana_type = ""
        reason = "self_reprimand"
        found = False
        for effect_id in list(effect_list.effect_entities):
            effect = self._effect(effect_id)
            if effect is None or effect.slug != "self_reprimand":
                continue
            found = True
            metadata = effect.metadata or {}
            bonus_damage += self._coerce_positive(metadata.get("bonus_damage"), default=1)
            mana_amount += self._coerce_positive(metadata.get("mana_amount"), default=1)
            mana_type = str(metadata.get("mana_type", mana_type or "blood"))
            reason = str(metadata.get("reason", reason))
        if not found:
            return None
        return bonus_damage, mana_amount, mana_type, reason

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

    def _find_opponent(self, owner: int) -> int | None:
        for entity, _ in self.world.get_component(AbilityListOwner):
            if entity != owner:
                return entity
        return None

    @staticmethod
    def _coerce_positive(value, *, default: int = 0) -> int:
        try:
            amount = int(value)
        except (TypeError, ValueError):
            return default
        return amount if amount > 0 else default
