from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.components.ability_cooldown import AbilityCooldown


def create_ability_thorned_ward(world: World) -> int:
    """Grant the caster a retaliatory thorns aura for several turns."""

    return world.create_entity(
        Ability(
            name="thorned_ward",
            kind="active",
            cost={"nature": 4},
            description="Gain thorns for three turns, returning 2 damage to attackers hit via abilities or witchfire.",
            cooldown=1,
            ends_turn=False,
        ),
        AbilityTarget(target_type="self", max_targets=0),
        AbilityEffects(
            effects=(
                AbilityEffectSpec(
                    slug="thorns",
                    target="pending_target_or_self",
                    turns=3,
                    metadata={
                        "amount": 2,
                        "reason": "thorns",
                        "stack_key": "thorns",
                    },
                ),
            )
        ),
        AbilityCooldown(),
    )
