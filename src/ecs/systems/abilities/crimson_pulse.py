from __future__ import annotations

from ecs.events.bus import (
    EVENT_ABILITY_EFFECT_APPLIED,
    EVENT_ANIMATION_START,
    EVENT_BOARD_CHANGED,
    EVENT_CASCADE_COMPLETE,
    EVENT_MATCH_CLEARED,
)
from ecs.systems.abilities.base import AbilityContext, AbilityResolver
from ecs.systems.board_ops import clear_tiles_with_cascade
from ecs.systems.turn_state_utils import get_or_create_turn_state


class CrimsonPulseResolver:
    """Clears a 3x3 area around the targeted tile and triggers cascades."""

    name = "crimson_pulse"

    def resolve(self, ctx: AbilityContext) -> None:
        row = ctx.pending.row
        col = ctx.pending.col
        if row is None or col is None:
            return

        positions = [
            (r, c)
            for r in range(row - 1, row + 2)
            for c in range(col - 1, col + 2)
        ]

        colored, typed, gravity_moves, cascades, new_tiles = clear_tiles_with_cascade(ctx.world, positions)

        ctx.event_bus.emit(
            EVENT_ABILITY_EFFECT_APPLIED,
            ability_entity=ctx.ability_entity,
            affected=positions,
        )

        triggered_animation = False

        if colored:
            animated_moves = [
                {"from": move.source, "to": move.target, "type_name": move.type_name}
                for move in gravity_moves
            ]
            affected_positions = [(row, col) for row, col, _ in colored]
            ctx.event_bus.emit(
                EVENT_BOARD_CHANGED,
                reason="ability_effect",
                positions=affected_positions,
                new_tiles=new_tiles,
                gravity_moves=gravity_moves,
            )
            if animated_moves:
                ctx.event_bus.emit(
                    EVENT_ANIMATION_START,
                    kind="fall",
                    items=animated_moves,
                )
                triggered_animation = True
            elif new_tiles:
                ctx.event_bus.emit(
                    EVENT_ANIMATION_START,
                    kind="refill",
                    items=new_tiles,
                )
                triggered_animation = True

        if typed:
            ctx.event_bus.emit(
                EVENT_MATCH_CLEARED,
                positions=[(row, col) for row, col, _ in typed],
                types=typed,
                owner_entity=ctx.active_owner,
            )

        state = get_or_create_turn_state(ctx.world)
        if triggered_animation:
            state.cascade_active = True
            state.cascade_observed = True
            if state.cascade_depth <= 0:
                state.cascade_depth = 1
        else:
            ctx.event_bus.emit(
                EVENT_CASCADE_COMPLETE,
                depth=0,
                source="ability",
            )


def create_resolver() -> AbilityResolver:
    return CrimsonPulseResolver()