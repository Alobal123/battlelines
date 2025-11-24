from __future__ import annotations

from typing import Dict, Iterable, List

from esper import World

from ecs.components.effect import Effect
from ecs.components.effect_list import EffectList
from ecs.events.bus import (
    EVENT_EFFECT_APPLY,
    EVENT_EFFECT_REMOVE,
    EVENT_MATCH_CLEARED,
    EventBus,
)
from ecs.systems.board_ops import get_entity_at


class GuardedTileEffectSystem:
    """Triggers retaliation damage when guarded tiles are cleared."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        event_bus.subscribe(EVENT_MATCH_CLEARED, self.on_match_cleared)

    def on_match_cleared(self, sender, **payload) -> None:
        positions: Iterable[tuple[int, int]] = payload.get("positions") or ()
        match_owner = payload.get("owner_entity")
        if match_owner is None:
            return
        for row, col in positions:
            tile_entity = get_entity_at(self.world, row, col)
            if tile_entity is None:
                continue
            guard_effects = self._collect_guard_effects(tile_entity)
            if not guard_effects:
                continue
            for effect_entity, effect in guard_effects:
                source_owner = effect.metadata.get("source_owner")
                if source_owner is not None and source_owner == match_owner:
                    continue
                amount = self._coerce_int(
                    effect.metadata.get("damage", effect.metadata.get("amount", 1))
                )
                if amount <= 0:
                    amount = 1
                reason = str(effect.metadata.get("reason", "guarded_tile"))
                metadata: Dict[str, object] = {
                    "amount": amount,
                    "reason": reason,
                    "source_owner": source_owner,
                }
                self.event_bus.emit(
                    EVENT_EFFECT_APPLY,
                    owner_entity=match_owner,
                    source_entity=effect.source_entity,
                    slug="damage",
                    metadata=metadata,
                )
                self.event_bus.emit(
                    EVENT_EFFECT_REMOVE,
                    effect_entity=effect_entity,
                    reason="guarded_triggered",
                )

    def _collect_guard_effects(self, tile_entity: int) -> List[tuple[int, Effect]]:
        try:
            effect_list: EffectList = self.world.component_for_entity(tile_entity, EffectList)
        except KeyError:
            return []
        results: List[tuple[int, Effect]] = []
        for effect_entity in list(effect_list.effect_entities):
            try:
                effect = self.world.component_for_entity(effect_entity, Effect)
            except KeyError:
                continue
            if effect.slug == "tile_guarded":
                results.append((effect_entity, effect))
        return results

    @staticmethod
    def _coerce_int(value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
