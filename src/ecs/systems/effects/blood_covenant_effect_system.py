from __future__ import annotations

from esper import World

from ecs.components.effect import Effect
from ecs.components.effect_list import EffectList
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.events.bus import EVENT_EFFECT_APPLY, EVENT_TURN_ADVANCED, EventBus


class BloodCovenantEffectSystem:
    """Deals equal damage to both combatants at the start of the owner's turn."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_TURN_ADVANCED, self._on_turn_advanced)

    def _on_turn_advanced(self, sender, **payload) -> None:
        owner = payload.get("new_owner")
        if owner is None:
            return
        totals = self._collect_effect_totals(int(owner))
        if totals is None:
            return
        amount, reason = totals
        if amount <= 0:
            return
        self._emit_damage(int(owner), int(owner), amount, reason)
        opponent = self._find_opponent(int(owner))
        if opponent is None:
            return
        self._emit_damage(int(owner), opponent, amount, reason)

    def _collect_effect_totals(self, owner: int) -> tuple[int, str] | None:
        effect_list = self._effect_list(owner)
        if effect_list is None:
            return None
        amount = 0
        reason = "blood_covenant"
        found = False
        for effect_id in list(effect_list.effect_entities):
            effect = self._effect(effect_id)
            if effect is None or effect.slug != "blood_covenant":
                continue
            found = True
            metadata = effect.metadata or {}
            amount += self._coerce_positive(metadata.get("amount"), default=1)
            reason = str(metadata.get("reason", reason))
        if not found or amount <= 0:
            return None
        return amount, reason

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

    def _emit_damage(self, source_owner: int, target_entity: int, amount: int, reason: str) -> None:
        self.event_bus.emit(
            EVENT_EFFECT_APPLY,
            owner_entity=target_entity,
            source_entity=None,
            slug="damage",
            turns=0,
            metadata={
                "amount": amount,
                "reason": reason,
                "source_owner": source_owner,
            },
        )

    @staticmethod
    def _coerce_positive(value, *, default: int = 0) -> int:
        try:
            amount = int(value)
        except (TypeError, ValueError):
            return default
        return amount if amount > 0 else default
