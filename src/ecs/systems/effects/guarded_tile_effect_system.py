from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple

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
        match_owner = payload.get("owner_entity")
        if match_owner is None:
            return
        for row, col, entity in self._iter_source_tiles(payload):
            tile_entity = entity if entity is not None else get_entity_at(self.world, row, col)
            if tile_entity is None:
                continue
            guard_effects = self._collect_guard_effects(tile_entity)
            if not guard_effects:
                continue
            for effect_entity, effect in guard_effects:
                source_owner = effect.metadata.get("source_owner")
                same_owner = source_owner is not None and source_owner == match_owner
                if same_owner:
                    effect_reason = str(effect.metadata.get("reason", ""))
                    if effect_reason == "guard":
                        self.event_bus.emit(
                            EVENT_EFFECT_REMOVE,
                            effect_entity=effect_entity,
                            reason="guarded_owner_cleared",
                        )
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

    def _iter_source_tiles(self, payload: Dict) -> Iterable[Tuple[int, int, int | None]]:
        entries = payload.get("entities")
        if entries:
            for entry in entries:
                row: int | None = None
                col: int | None = None
                entity: int | None = None
                if isinstance(entry, dict):
                    row = entry.get("row")
                    col = entry.get("col")
                    entity = entry.get("entity")
                elif isinstance(entry, Sequence) and len(entry) >= 3:
                    row, col, entity = entry[0], entry[1], entry[2]
                elif isinstance(entry, Sequence) and len(entry) == 2:
                    row, col = entry[0], entry[1]
                if row is None or col is None:
                    continue
                try:
                    norm_row = int(row)
                    norm_col = int(col)
                except (TypeError, ValueError):
                    continue
                try:
                    entity_id = int(entity) if entity is not None else None
                except (TypeError, ValueError):
                    entity_id = None
                yield (norm_row, norm_col, entity_id)
            return

        positions: Iterable[tuple[int, int]] = payload.get("positions") or ()
        for row, col in positions:
            if row is None or col is None:
                continue
            try:
                norm_row = int(row)
                norm_col = int(col)
            except (TypeError, ValueError):
                continue
            yield (norm_row, norm_col, None)

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
