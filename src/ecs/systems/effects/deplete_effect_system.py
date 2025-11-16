from __future__ import annotations

from typing import Tuple

from esper import World

from ecs.components.effect import Effect
from ecs.components.tile_bank import TileBank
from ecs.systems.effects.bank_effect_helpers import drain_bank_counts
from ecs.events.bus import (
    EVENT_EFFECT_APPLIED,
    EVENT_EFFECT_REFRESHED,
    EVENT_EFFECT_REMOVE,
    EVENT_TILE_BANK_CHANGED,
    EVENT_TILE_BANK_DEPLETED,
    EventBus,
)


class DepleteEffectSystem:
    """Handles immediate mana depletion effects when they are applied."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_EFFECT_APPLIED, self._on_effect_event)
        self.event_bus.subscribe(EVENT_EFFECT_REFRESHED, self._on_effect_event)

    def _on_effect_event(self, sender, **payload) -> None:
        if payload.get("slug") != "deplete":
            return
        effect_entity = payload.get("effect_entity")
        if effect_entity is None:
            return
        try:
            effect = self.world.component_for_entity(effect_entity, Effect)
        except KeyError:
            return
        owner_entity = effect.owner_entity
        if owner_entity is None:
            self._remove_effect(effect_entity, reason="no_owner")
            return
        amount = self._coerce_int(effect.metadata.get("amount"))
        if amount <= 0:
            self._remove_effect(effect_entity, reason="noop")
            return
        bank_info = self._find_bank(owner_entity)
        if bank_info is None:
            self._remove_effect(effect_entity, reason="no_bank")
            return
        bank_entity, bank = bank_info
        mode = str(effect.metadata.get("mode", "type")).lower()
        deltas = drain_bank_counts(bank, amount, effect.metadata)
        context_ref = effect.metadata.get("_ability_context")
        if isinstance(context_ref, dict):
            total_key = effect.metadata.get("context_write")
            if isinstance(total_key, str):
                context_ref[total_key] = sum(deltas.values()) if deltas else 0
            map_key = effect.metadata.get("context_write_map")
            if isinstance(map_key, str):
                context_ref[map_key] = dict(deltas)
        if deltas:
            self.event_bus.emit(
                EVENT_TILE_BANK_CHANGED,
                entity=bank_entity,
                counts=bank.counts.copy(),
            )
            self.event_bus.emit(
                EVENT_TILE_BANK_DEPLETED,
                entity=bank_entity,
                owner_entity=owner_entity,
                deltas=deltas,
                reason=str(effect.metadata.get("reason", effect.slug)),
                mode=mode,
                source_owner=effect.metadata.get("source_owner"),
                effect_entity=effect_entity,
            )
            self._remove_effect(effect_entity, reason="resolved")
        else:
            self._remove_effect(effect_entity, reason="noop")

    def _find_bank(self, owner_entity: int) -> Tuple[int, TileBank] | None:
        for entity, bank in self.world.get_component(TileBank):
            if bank.owner_entity == owner_entity:
                return entity, bank
        return None

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