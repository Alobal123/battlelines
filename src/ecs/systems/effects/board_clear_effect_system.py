from __future__ import annotations

from typing import List, Tuple

from esper import World

from ecs.components.effect import Effect
from ecs.events.bus import (
    EVENT_ABILITY_EFFECT_APPLIED,
    EVENT_ANIMATION_START,
    EVENT_BOARD_CHANGED,
    EVENT_CASCADE_COMPLETE,
    EVENT_EFFECT_APPLIED,
    EVENT_EFFECT_REFRESHED,
    EVENT_EFFECT_REMOVE,
    EVENT_MATCH_CLEARED,
    EventBus,
)
from ecs.systems.board_ops import clear_tiles_with_cascade, GravityMove
from ecs.systems.turn_state_utils import get_or_create_turn_state

Position = Tuple[int, int]


class BoardClearEffectSystem:
    """Resolves area-based board clear effects (e.g., crimson pulse)."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_EFFECT_APPLIED, self._on_effect_event)
        self.event_bus.subscribe(EVENT_EFFECT_REFRESHED, self._on_effect_event)

    def _on_effect_event(self, sender, **payload) -> None:
        if payload.get("slug") != "board_clear_area":
            return
        effect_entity = payload.get("effect_entity")
        if effect_entity is None:
            return
        try:
            effect = self.world.component_for_entity(effect_entity, Effect)
        except KeyError:
            return
        metadata = effect.metadata or {}
        positions = self._resolve_positions(metadata)
        if not positions:
            self._emit_noop(effect, metadata)
            self._remove_effect(effect_entity, reason="resolved")
            return

        colored, typed, gravity_moves, cascades, new_tiles = clear_tiles_with_cascade(self.world, positions)

        affected_positions = [(row, col) for row, col, _ in colored]
        ability_entity = effect.source_entity
        if ability_entity is not None:
            self.event_bus.emit(
                EVENT_ABILITY_EFFECT_APPLIED,
                ability_entity=ability_entity,
                affected=affected_positions,
            )

        triggered_animation = False
        reason = metadata.get("reason", effect.slug)
        if affected_positions:
            animated_moves = self._serialize_gravity_moves(gravity_moves)
            self.event_bus.emit(
                EVENT_BOARD_CHANGED,
                reason="ability_effect",
                positions=affected_positions,
                new_tiles=new_tiles,
                gravity_moves=gravity_moves,
            )
            if animated_moves:
                self.event_bus.emit(
                    EVENT_ANIMATION_START,
                    kind="fall",
                    items=animated_moves,
                )
                triggered_animation = True
            elif new_tiles:
                self.event_bus.emit(
                    EVENT_ANIMATION_START,
                    kind="refill",
                    items=new_tiles,
                )
                triggered_animation = True

        if typed:
            owner_entity = metadata.get("source_owner")
            self.event_bus.emit(
                EVENT_MATCH_CLEARED,
                positions=[(row, col) for row, col, _ in typed],
                types=typed,
                owner_entity=owner_entity,
                reason=reason,
            )

        state = get_or_create_turn_state(self.world)
        if triggered_animation:
            state.cascade_active = True
            state.cascade_observed = True
            depth = cascades or 1
            if state.cascade_depth < depth:
                state.cascade_depth = depth
        else:
            self.event_bus.emit(
                EVENT_CASCADE_COMPLETE,
                depth=0,
                source=metadata.get("source", "ability"),
            )

        self._remove_effect(effect_entity, reason="resolved")

    def _emit_noop(self, effect: Effect, metadata: dict) -> None:
        ability_entity = effect.source_entity
        if ability_entity is not None:
            self.event_bus.emit(
                EVENT_ABILITY_EFFECT_APPLIED,
                ability_entity=ability_entity,
                affected=[],
            )
        state = get_or_create_turn_state(self.world)
        state.cascade_active = False
        state.cascade_depth = 0
        state.cascade_observed = False
        self.event_bus.emit(
            EVENT_CASCADE_COMPLETE,
            depth=0,
            source=metadata.get("source", "ability"),
        )

    def _resolve_positions(self, metadata: dict) -> List[Position]:
        explicit = metadata.get("positions")
        if explicit:
            return [
                (int(pos[0]), int(pos[1]))
                for pos in explicit
                if isinstance(pos, (list, tuple)) and len(pos) == 2
            ]
        origin_row = metadata.get("origin_row")
        origin_col = metadata.get("origin_col")
        if origin_row is None or origin_col is None:
            return []
        dims = self._board_dimensions()
        if dims is None:
            return []
        rows, cols = dims
        shape = str(metadata.get("shape", "square")).lower()
        radius = metadata.get("radius", 0)
        try:
            radius = int(radius)
        except (TypeError, ValueError):
            radius = 0
        positions: List[Position] = []
        if shape == "square":
            for r in range(origin_row - radius, origin_row + radius + 1):
                for c in range(origin_col - radius, origin_col + radius + 1):
                    if 0 <= r < rows and 0 <= c < cols:
                        positions.append((r, c))
        else:
            # Default to single tile at origin for unsupported shapes.
            if 0 <= origin_row < rows and 0 <= origin_col < cols:
                positions.append((origin_row, origin_col))
        return positions

    def _board_dimensions(self) -> Tuple[int, int] | None:
        from ecs.components.board import Board

        boards = list(self.world.get_component(Board))
        if not boards:
            return None
        board = boards[0][1]
        return board.rows, board.cols

    @staticmethod
    def _serialize_gravity_moves(moves: List[GravityMove]) -> List[dict]:
        return [
            {"from": move.source, "to": move.target, "type_name": move.type_name}
            for move in moves
        ]

    def _remove_effect(self, effect_entity: int, *, reason: str) -> None:
        self.event_bus.emit(
            EVENT_EFFECT_REMOVE,
            effect_entity=effect_entity,
            reason=reason,
        )
