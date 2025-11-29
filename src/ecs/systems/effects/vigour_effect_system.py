from __future__ import annotations

from esper import World

from ecs.components.effect import Effect
from ecs.components.effect_list import EffectList
from ecs.events.bus import EVENT_EFFECT_APPLY, EVENT_HEALTH_CHANGED, EventBus
from ecs.utils.combatants import find_primary_opponent


class VigourEffectSystem:
    """Converts overhealing into direct damage against the opposing combatant."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_HEALTH_CHANGED, self._on_health_changed)

    def _on_health_changed(self, sender, **payload) -> None:
        overheal = self._coerce_positive(payload.get("overheal"))
        if overheal <= 0:
            return
        owner = payload.get("entity")
        if owner is None:
            return
        totals = self._collect_totals(int(owner))
        if totals is None:
            return
        multiplier, reason = totals
        damage = overheal * multiplier
        if damage <= 0:
            return
        opponent = self._find_opponent(int(owner))
        if opponent is None:
            return
        self.event_bus.emit(
            EVENT_EFFECT_APPLY,
            owner_entity=opponent,
            source_entity=None,
            slug="damage",
            turns=0,
            metadata={
                "amount": damage,
                "reason": reason,
                "source_owner": owner,
            },
        )

    def _collect_totals(self, owner: int) -> tuple[int, str] | None:
        effect_list = self._effect_list(owner)
        if effect_list is None:
            return None
        multiplier = 0
        reason = "vigour"
        found = False
        for effect_id in list(effect_list.effect_entities):
            effect = self._effect(effect_id)
            if effect is None or effect.slug != "vigour":
                continue
            found = True
            metadata = effect.metadata or {}
            multiplier += self._coerce_positive(metadata.get("multiplier"), default=1)
            reason = str(metadata.get("reason", reason))
        if not found or multiplier <= 0:
            return None
        return multiplier, reason

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
        return find_primary_opponent(self.world, owner)

    @staticmethod
    def _coerce_positive(value, *, default: int = 0) -> int:
        try:
            amount = int(value)
        except (TypeError, ValueError):
            return default
        return amount if amount > 0 else default
