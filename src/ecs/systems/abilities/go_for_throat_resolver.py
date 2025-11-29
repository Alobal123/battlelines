from __future__ import annotations

from ecs.components.effect import Effect
from ecs.components.effect_list import EffectList
from ecs.events.bus import EVENT_ABILITY_EFFECT_APPLIED, EVENT_CASCADE_COMPLETE
from ecs.systems.abilities.base import AbilityContext, AbilityResolver, EffectDrivenAbilityResolver
from ecs.systems.turn_state_utils import get_or_create_turn_state
from ecs.utils.combatants import find_primary_opponent


class GoForThroatResolver(AbilityResolver):
    """Ability resolver that scales damage with accumulated bleeding stacks."""

    name = "go_for_throat"

    def __init__(self) -> None:
        self._effect_helper = EffectDrivenAbilityResolver()

    def resolve(self, ctx: AbilityContext) -> None:  # pragma: no cover - verified in integration tests
        bleeding_charges = self._bleeding_charge_units(ctx)
        ctx.scratchpad["go_for_throat_damage"] = 3 + (2 * bleeding_charges)
        affected = self._effect_helper._apply_declared_effects(ctx)
        ctx.event_bus.emit(
            EVENT_ABILITY_EFFECT_APPLIED,
            ability_entity=ctx.ability_entity,
            affected=affected,
        )
        state = get_or_create_turn_state(ctx.world)
        if not state.cascade_observed:
            ctx.event_bus.emit(EVENT_CASCADE_COMPLETE, depth=0)

    def _bleeding_charge_units(self, ctx: AbilityContext) -> int:
        opponent = find_primary_opponent(ctx.world, ctx.owner_entity)
        if opponent is None:
            return 0
        try:
            effect_list = ctx.world.component_for_entity(opponent, EffectList)
        except KeyError:
            return 0
        count = 0
        for effect_entity in list(effect_list.effect_entities):
            try:
                effect = ctx.world.component_for_entity(effect_entity, Effect)
            except KeyError:
                continue
            if effect.owner_entity != opponent:
                continue
            if effect.slug != "bleeding":
                continue
            stacks = max(0, int(getattr(effect, "count", 0)))
            if stacks <= 0:
                continue
            count += stacks // 5
        return count
