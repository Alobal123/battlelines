from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, List

from esper import World

from ecs.components.effect import Effect
from ecs.components.effect_list import EffectList
from ecs.events.bus import (
    EVENT_EFFECT_REMOVE,
    EVENT_HEALTH_DAMAGE,
    EVENT_TILE_BANK_CHANGED,
    EventBus,
)


class BleedingEffectSystem:
    """Applies bleeding damage when the afflicted entity gains blood mana."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_TILE_BANK_CHANGED, self._on_bank_changed)

    def _on_bank_changed(self, sender, **payload) -> None:
        source_owner = payload.get("owner_entity")
        if source_owner is None:
            return
        delta = payload.get("delta") or {}
        amount = self._coerce_amount(delta.get("blood"))
        if amount <= 0:
            return
        self._apply_from_source(source_owner, amount)

    def _apply_from_source(self, source_owner: int, amount: int) -> None:
        if amount <= 0:
            return
        applied = self._apply_to_afflicted_targets(source_owner, amount)
        if applied:
            return
        # Fallback: if no targets reference this source, attempt to apply directly to the owner.
        self._apply_direct(owner=source_owner, amount=amount)

    def _apply_to_afflicted_targets(self, source_owner: int, amount: int) -> bool:
        groups: DefaultDict[int, List[int]] = defaultdict(list)
        for owner, effect_list in self.world.get_component(EffectList):
            for effect_entity in list(effect_list.effect_entities):
                effect = self._effect(effect_entity)
                if effect is None or effect.slug != "bleeding":
                    continue
                if effect.metadata.get("source_owner") != source_owner:
                    continue
                groups[owner].append(effect_entity)
        if not groups:
            return False
        for owner, effect_entities in groups.items():
            self._apply_effects(owner, effect_entities, amount)
        return True

    def _apply_direct(self, owner: int, amount: int) -> None:
        effect_list = self._effect_list(owner)
        if effect_list is None:
            return
        filtered = []
        for effect_entity in list(effect_list.effect_entities):
            effect = self._effect(effect_entity)
            if effect is None or effect.slug != "bleeding":
                continue
            source_owner = effect.metadata.get("source_owner")
            if source_owner is not None and source_owner != owner:
                continue
            filtered.append(effect_entity)
        if not filtered:
            return
        self._apply_effects(owner, filtered, amount)

    def _apply_effects(self, owner: int, effect_entities: List[int], amount: int) -> None:
        remaining = amount
        for effect_entity in effect_entities:
            remaining = self._apply_effect_entity(owner, effect_entity, remaining)
            if remaining <= 0:
                break

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

    def _apply_effect_entity(self, target_entity: int, effect_entity: int, amount: int) -> int:
        effect = self._effect(effect_entity)
        if effect is None or effect.slug != "bleeding":
            return amount
        stacks = max(0, int(getattr(effect, "count", 0)))
        if stacks <= 0:
            self._remove_effect(effect_entity)
            return amount
        damage = min(amount, stacks)
        if damage <= 0:
            return amount
        reason = str(effect.metadata.get("reason", "bleeding"))
        source_owner = effect.metadata.get("source_owner")
        self.event_bus.emit(
            EVENT_HEALTH_DAMAGE,
            source_owner=source_owner,
            target_entity=target_entity,
            amount=damage,
            reason=reason,
            effect_entity=effect_entity,
            effect_slug="bleeding",
        )
        effect.count = max(0, stacks - damage)
        if effect.count <= 0:
            self._remove_effect(effect_entity)
        return max(0, amount - damage)

    def _remove_effect(self, effect_entity: int) -> None:
        self.event_bus.emit(
            EVENT_EFFECT_REMOVE,
            effect_entity=effect_entity,
            reason="bleeding_depleted",
        )
