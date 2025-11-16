from __future__ import annotations

from esper import World

from ecs.components.effect import Effect
from ecs.components.tile_bank import TileBank
from ecs.events.bus import (
    EventBus,
    EVENT_EFFECT_APPLIED,
    EVENT_EFFECT_REFRESHED,
    EVENT_MANA_DRAIN,
    EVENT_TILE_BANK_CHANGED,
    EVENT_TILE_BANK_GAINED,
)
from ecs.systems.effects.bank_effect_helpers import drain_bank_counts


class ManaDrainEffectSystem:
    """Handles mana_drain effects by consuming mana and emitting drain events."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_EFFECT_APPLIED, self._on_effect_event)
        self.event_bus.subscribe(EVENT_EFFECT_REFRESHED, self._on_effect_event)

    def _on_effect_event(self, sender, **payload) -> None:
        if payload.get("slug") != "mana_drain":
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
        if not bank.counts:
            self._remove_effect(effect_entity, reason="empty_bank")
            return
        mode = str(effect.metadata.get("mode", "type")).lower()
        drained = drain_bank_counts(bank, amount, effect.metadata)
        total_drained = sum(drained.values())
        if total_drained > 0:
            self.event_bus.emit(
                EVENT_TILE_BANK_CHANGED,
                entity=bank_entity,
                counts=bank.counts.copy(),
            )
            gained = self._grant_to_source_owner(effect.metadata.get("source_owner"), drained)
            self.event_bus.emit(
                EVENT_MANA_DRAIN,
                target_entity=owner_entity,
                source_owner=effect.metadata.get("source_owner"),
                amount=total_drained,
                reason=str(effect.metadata.get("reason", effect.slug)),
                breakdown=drained,
                mode=mode,
                gained=gained,
            )
            self._remove_effect(effect_entity, reason="resolved")
        else:
            self._remove_effect(effect_entity, reason="noop")

    def _grant_to_source_owner(self, source_owner, drained: dict[str, int]) -> dict[str, int]:
        if not isinstance(source_owner, int) or not drained:
            return {}
        source_info = self._find_bank(source_owner)
        if source_info is None:
            return {}
        source_entity, source_bank = source_info
        gained: dict[str, int] = {}
        for type_name, amount in drained.items():
            if amount <= 0:
                continue
            source_bank.add(type_name, amount)
            gained[type_name] = gained.get(type_name, 0) + amount
        if not gained:
            return {}
        self.event_bus.emit(
            EVENT_TILE_BANK_CHANGED,
            entity=source_entity,
            counts=source_bank.counts.copy(),
        )
        for type_name, amount in gained.items():
            self.event_bus.emit(
                EVENT_TILE_BANK_GAINED,
                owner_entity=source_owner,
                bank_entity=source_entity,
                type_name=type_name,
                amount=amount,
                reason="mana_drain",
            )
        return gained

    def _find_bank(self, owner_entity: int):
        for entity, bank in self.world.get_component(TileBank):
            if bank.owner_entity == owner_entity:
                return entity, bank
        return None

    def _remove_effect(self, effect_entity: int, *, reason: str) -> None:
        from ecs.events.bus import EVENT_EFFECT_REMOVE

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
