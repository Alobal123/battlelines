from __future__ import annotations

from esper import World

from ecs.components.tile import TileType
from ecs.events.bus import EVENT_ABILITY_EFFECT_APPLIED, EVENT_CASCADE_COMPLETE
from ecs.systems.abilities.base import AbilityContext, AbilityResolver, EffectDrivenAbilityResolver
from ecs.systems.turn_state_utils import get_or_create_turn_state


class BeeStingResolver(AbilityResolver):
    """Ability resolver that scales damage with nature tiles on the board."""

    name = "bee_sting"

    def __init__(self) -> None:
        self._effect_helper = EffectDrivenAbilityResolver()

    def resolve(self, ctx: AbilityContext) -> None:  # pragma: no cover - exercised in tests
        ctx.scratchpad["bee_sting_amount"] = self._nature_tile_count(ctx.world)
        affected = self._effect_helper._apply_declared_effects(ctx)
        ctx.event_bus.emit(
            EVENT_ABILITY_EFFECT_APPLIED,
            ability_entity=ctx.ability_entity,
            affected=affected,
        )
        state = get_or_create_turn_state(ctx.world)
        if not state.cascade_observed:
            ctx.event_bus.emit(EVENT_CASCADE_COMPLETE, depth=0)

    @staticmethod
    def _nature_tile_count(world: World) -> int:
        try:
            return sum(1 for _, tile in world.get_component(TileType) if tile.type_name == "nature")
        except Exception:
            return 0
