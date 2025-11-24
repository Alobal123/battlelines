from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

from esper import World

from ecs.components.effect import Effect
from ecs.components.active_switch import ActiveSwitch
from ecs.components.tile import TileType
from ecs.events.bus import (
    EVENT_ABILITY_EFFECT_APPLIED,
    EVENT_BOARD_CHANGED,
    EVENT_CASCADE_COMPLETE,
    EVENT_EFFECT_APPLIED,
    EVENT_EFFECT_REFRESHED,
    EVENT_EFFECT_REMOVE,
    EVENT_MATCH_CLEARED,
    EventBus,
)
from ecs.systems.board_ops import get_entity_at, transform_tiles_to_type, find_all_matches
from ecs.systems.turn_state_utils import get_or_create_turn_state

class BoardTransformEffectSystem:
    """Resolves board transformation effects created by abilities like tactical shift."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_EFFECT_APPLIED, self._on_effect_event)
        self.event_bus.subscribe(EVENT_EFFECT_REFRESHED, self._on_effect_event)

    def _on_effect_event(self, sender, **payload) -> None:
        if payload.get("slug") != "board_transform_type":
            return
        effect_entity = payload.get("effect_entity")
        if effect_entity is None:
            return
        try:
            effect = self.world.component_for_entity(effect_entity, Effect)
        except KeyError:
            return
        metadata = effect.metadata or {}
        affected: List[Tuple[int, int]] = []
        types_payload: List[Tuple[int, int, str]] = []

        positions_meta = metadata.get("positions")
        if positions_meta:
            affected, types_payload = self._apply_explicit_transforms(positions_meta, metadata)
            matches_present = bool(find_all_matches(self.world)) if affected else False
        else:
            target_type = metadata.get("target_type")
            origin_row = metadata.get("origin_row")
            origin_col = metadata.get("origin_col")
            if not target_type or origin_row is None or origin_col is None:
                self._remove_effect(effect_entity, reason="resolved")
                return
            affected = transform_tiles_to_type(
                self.world,
                int(origin_row),
                int(origin_col),
                str(target_type),
            )
            matches_present = bool(find_all_matches(self.world)) if affected else False
            types_payload = [(row, col, str(target_type)) for row, col in affected]
        ability_entity = effect.source_entity
        if ability_entity is not None:
            self.event_bus.emit(
                EVENT_ABILITY_EFFECT_APPLIED,
                ability_entity=ability_entity,
                affected=affected,
            )

        if affected:
            reason = metadata.get("reason", effect.slug)
            self.event_bus.emit(
                EVENT_BOARD_CHANGED,
                reason="ability_effect",
                positions=affected,
                types=types_payload,
            )
            owner_entity = metadata.get("source_owner")
            if self._should_emit_match_cleared(metadata):
                self.event_bus.emit(
                    EVENT_MATCH_CLEARED,
                    positions=affected,
                    types=types_payload,
                    owner_entity=owner_entity,
                    reason=reason,
                )

        state = get_or_create_turn_state(self.world)
        if matches_present:
            state.cascade_observed = True
        else:
            state.cascade_active = False
            state.cascade_depth = 0
            state.cascade_observed = False

        self._remove_effect(effect_entity, reason="resolved")

    def _remove_effect(self, effect_entity: int, *, reason: str) -> None:
        self.event_bus.emit(
            EVENT_EFFECT_REMOVE,
            effect_entity=effect_entity,
            reason=reason,
        )

    def _apply_explicit_transforms(
        self,
        positions_meta: Iterable,
        metadata: dict,
    ) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int, str]]]:
        positions: List[Tuple[int, int]] = []
        types_payload: List[Tuple[int, int, str]] = []
        targets = self._coerce_target_types(metadata.get("target_types"))
        fallback = metadata.get("target_type")
        for index, raw_pos in enumerate(positions_meta):
            position = self._coerce_position(raw_pos)
            if position is None:
                continue
            target_type = self._select_target_type(index, targets, fallback)
            if target_type is None:
                continue
            row, col = position
            entity = get_entity_at(self.world, row, col)
            if entity is None:
                continue
            try:
                switch: ActiveSwitch = self.world.component_for_entity(entity, ActiveSwitch)
                if not switch.active:
                    continue
                tile: TileType = self.world.component_for_entity(entity, TileType)
            except KeyError:
                continue
            tile.type_name = target_type
            positions.append((row, col))
            types_payload.append((row, col, target_type))
        return positions, types_payload

    @staticmethod
    def _should_emit_match_cleared(metadata: dict) -> bool:
        value = metadata.get("emit_match_cleared", True)
        return bool(value)

    @staticmethod
    def _coerce_target_types(raw: object) -> List[str]:
        if isinstance(raw, (list, tuple)):
            return [str(item) for item in raw if item]
        return []

    @staticmethod
    def _select_target_type(index: int, targets: Sequence[str], fallback: object) -> str | None:
        if 0 <= index < len(targets):
            candidate = targets[index]
            if candidate:
                return candidate
        if fallback:
            return str(fallback)
        return None

    @staticmethod
    def _coerce_position(raw: object) -> Tuple[int, int] | None:
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            try:
                return int(raw[0]), int(raw[1])
            except (TypeError, ValueError):
                return None
        if isinstance(raw, dict):
            row = raw.get("row")
            col = raw.get("col")
            try:
                if row is None or col is None:
                    return None
                return int(row), int(col)
            except (TypeError, ValueError):
                return None
        return None
