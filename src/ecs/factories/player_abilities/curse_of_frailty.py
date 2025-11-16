from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.components.ability_cooldown import AbilityCooldown


def create_ability_curse_of_frailty(world: World) -> int:
    """Apply a stacking frailty debuff that amplifies incoming damage."""
    return world.create_entity(
        Ability(
            name="curse_of_frailty",
            kind="active",
            cost={"hex": 3},
            description="Afflict the enemy with frailty for 3 turns. Each stack adds +1 damage taken.",
            cooldown=0,
            ends_turn=False,
        ),
        AbilityTarget(target_type="self", max_targets=0),
        AbilityEffects(
            effects=(
                AbilityEffectSpec(
                    slug="frailty",
                    target="opponent",
                    turns=3,
                    metadata={
                        "bonus": 1,
                        "reason": "curse_of_frailty",
                        "stacks": True,
                        "stack_key": "frailty",
                    },
                ),
            )
        ),
        AbilityCooldown(),
    )
