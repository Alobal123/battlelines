from __future__ import annotations

from ecs.events.bus import (
    EVENT_ABILITY_EFFECT_APPLIED,
    EVENT_BOARD_CHANGED,
    EVENT_CASCADE_COMPLETE,
    EVENT_MATCH_CLEARED,
)
from ecs.systems.abilities.base import AbilityContext, AbilityResolver
from ecs.systems.board_ops import get_tile_registry, transform_tiles_to_type
from ecs.systems.turn_state_utils import get_or_create_turn_state


class TacticalShiftResolver:
    """Converts all tiles of the selected tile's type to a configured target type."""

    name = "tactical_shift"

    def resolve(self, ctx: AbilityContext) -> None:
        row = ctx.pending.row
        col = ctx.pending.col
        if row is None or col is None:
            return
        registry = get_tile_registry(ctx.world)
        params = getattr(ctx.ability, "params", None)
        target_type = "ranged"
        if isinstance(params, dict):
            target_type = params.get("target_color", target_type)
        if target_type not in registry.types:
            target_type = "ranged"
        affected = transform_tiles_to_type(ctx.world, row, col, target_type)
        ctx.event_bus.emit(
            EVENT_ABILITY_EFFECT_APPLIED,
            ability_entity=ctx.ability_entity,
            affected=affected,
        )
        ctx.event_bus.emit(
            EVENT_BOARD_CHANGED,
            reason="ability_effect",
            positions=affected,
        )
        types_payload = [(r, c, target_type) for (r, c) in affected]
        ctx.event_bus.emit(
            EVENT_MATCH_CLEARED,
            positions=affected,
            types=types_payload,
            owner_entity=ctx.active_owner,
        )
        state = get_or_create_turn_state(ctx.world)
        if not state.cascade_observed:
            ctx.event_bus.emit(EVENT_CASCADE_COMPLETE, depth=0)


def create_resolver() -> AbilityResolver:
    return TacticalShiftResolver()
