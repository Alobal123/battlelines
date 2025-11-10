from __future__ import annotations

from ecs.events.bus import (
    EVENT_ABILITY_EFFECT_APPLIED,
    EVENT_CASCADE_COMPLETE,
    EVENT_EFFECT_APPLY,
)
from ecs.systems.abilities.base import AbilityContext, AbilityResolver
from ecs.systems.turn_state_utils import get_or_create_turn_state


class BolsterMoraleResolver:
    """Applies a morale boost effect to the targeted regiment."""

    name = "bolster_morale"

    def resolve(self, ctx: AbilityContext) -> None:
        target_entity = ctx.pending.target_entity
        params = getattr(ctx.ability, "params", {}) or {}
        bonus = params.get("morale_bonus", 20) if isinstance(params, dict) else 20
        turns = params.get("turns", 3) if isinstance(params, dict) else 3
        if target_entity is not None:
            ctx.event_bus.emit(
                EVENT_EFFECT_APPLY,
                owner_entity=target_entity,
                source_entity=ctx.ability_entity,
                slug="morale_boost",
                stacks=True,
                metadata={
                    "morale_bonus": bonus,
                    "turns": turns,
                    "caster_owner": ctx.owner_entity,
                },
                turns=turns,
            )
            ctx.event_bus.emit(
                EVENT_ABILITY_EFFECT_APPLIED,
                ability_entity=ctx.ability_entity,
                affected=[target_entity],
            )
        else:
            ctx.event_bus.emit(
                EVENT_ABILITY_EFFECT_APPLIED,
                ability_entity=ctx.ability_entity,
                affected=[],
            )
        state = get_or_create_turn_state(ctx.world)
        if not state.cascade_observed:
            ctx.event_bus.emit(EVENT_CASCADE_COMPLETE, depth=0)


def create_resolver() -> AbilityResolver:
    return BolsterMoraleResolver()
