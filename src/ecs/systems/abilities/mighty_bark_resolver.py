from __future__ import annotations

from ecs.components.effect import Effect
from ecs.events.bus import EVENT_ABILITY_EFFECT_APPLIED, EVENT_CASCADE_COMPLETE, EVENT_EFFECT_APPLY
from ecs.systems.abilities.base import AbilityContext, AbilityResolver
from ecs.systems.turn_state_utils import get_or_create_turn_state


class MightyBarkResolver(AbilityResolver):
    """Resolver for the Mastiffs' healing howl."""

    name = "mighty_bark"

    def resolve(self, ctx: AbilityContext) -> None:  # pragma: no cover - integration exercised elsewhere
        owner = ctx.owner_entity
        if owner is None:
            self._finalize(ctx, healed=False)
            return
        guarded_tiles = self._guarded_tile_count(ctx, owner)
        heal_per_tile = int(ctx.ability.params.get("heal_per_tile", 2))
        bonus = int(ctx.ability.params.get("flat_bonus", 0))
        amount = guarded_tiles * max(heal_per_tile, 0) + max(bonus, 0)
        if amount > 0:
            ctx.event_bus.emit(
                EVENT_EFFECT_APPLY,
                owner_entity=owner,
                source_entity=ctx.ability_entity,
                slug="heal",
                turns=0,
                metadata={
                    "amount": amount,
                    "reason": "mighty_bark",
                },
            )
            ctx.event_bus.emit(
                EVENT_ABILITY_EFFECT_APPLIED,
                ability_entity=ctx.ability_entity,
                affected=[owner],
            )
        else:
            ctx.event_bus.emit(
                EVENT_ABILITY_EFFECT_APPLIED,
                ability_entity=ctx.ability_entity,
                affected=[],
            )
        self._finalize(ctx, healed=amount > 0)

    def _guarded_tile_count(self, ctx: AbilityContext, owner_entity: int) -> int:
        count = 0
        for _, effect in ctx.world.get_component(Effect):
            if effect.slug != "tile_guarded":
                continue
            if effect.metadata.get("source_owner") != owner_entity:
                continue
            count += 1
        return count

    def _finalize(self, ctx: AbilityContext, *, healed: bool) -> None:
        state = get_or_create_turn_state(ctx.world)
        if not healed and state.cascade_observed:
            return
        if not state.cascade_observed:
            ctx.event_bus.emit(EVENT_CASCADE_COMPLETE, depth=0)
