from __future__ import annotations

from ecs.components.board import Board
from ecs.events.bus import (
    EVENT_ABILITY_EFFECT_APPLIED,
    EVENT_ANIMATION_START,
    EVENT_BOARD_CHANGED,
    EVENT_CASCADE_COMPLETE,
    EVENT_GRAVITY_APPLIED,
    EVENT_MATCH_CLEARED,
    EVENT_REFILL_COMPLETED,
)
from ecs.systems.abilities.base import AbilityContext, AbilityResolver
from ecs.systems.board_ops import clear_tiles_with_cascade
from ecs.systems.turn_state_utils import get_or_create_turn_state


class CrimsonPulseResolver:
    """Clears a 3x3 area centered on the targeted tile and triggers cascades."""

    name = "crimson_pulse"

    def resolve(self, ctx: AbilityContext) -> None:
        row = ctx.pending.row
        col = ctx.pending.col
        if row is None or col is None:
            return
        positions = self._area(ctx.world, row, col)
        _, types_payload, moves, cascades, new_tiles = clear_tiles_with_cascade(ctx.world, positions)
        ctx.event_bus.emit(
            EVENT_ABILITY_EFFECT_APPLIED,
            ability_entity=ctx.ability_entity,
            affected=positions,
        )
        ctx.event_bus.emit(
            EVENT_MATCH_CLEARED,
            positions=positions,
            types=types_payload,
            owner_entity=ctx.active_owner,
        )
        if moves:
            ctx.event_bus.emit(EVENT_GRAVITY_APPLIED, cascades=cascades)
            fall_payload = [
                {
                    "from": move.source,
                    "to": move.target,
                    "type_name": move.type_name,
                }
                for move in moves
            ]
            ctx.event_bus.emit(EVENT_ANIMATION_START, kind="fall", items=fall_payload)
        else:
            ctx.event_bus.emit(EVENT_GRAVITY_APPLIED, cascades=0)
            if new_tiles:
                ctx.event_bus.emit(EVENT_REFILL_COMPLETED, new_tiles=new_tiles)
                ctx.event_bus.emit(EVENT_ANIMATION_START, kind="refill", items=new_tiles)
        ctx.event_bus.emit(
            EVENT_BOARD_CHANGED,
            reason="ability_effect",
            positions=positions,
        )
        state = get_or_create_turn_state(ctx.world)
        if not state.cascade_observed:
            ctx.event_bus.emit(EVENT_CASCADE_COMPLETE, depth=0)

    @staticmethod
    def _area(world, row: int, col: int) -> list[tuple[int, int]]:
        board_comp = None
        for _, board in world.get_component(Board):
            board_comp = board
            break
        rows = board_comp.rows if board_comp else 8
        cols = board_comp.cols if board_comp else 8
        positions: list[tuple[int, int]] = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr = row + dr
                cc = col + dc
                if rr < 0 or cc < 0 or rr >= rows or cc >= cols:
                    continue
                positions.append((rr, cc))
        return positions


def create_resolver() -> AbilityResolver:
    return CrimsonPulseResolver()
