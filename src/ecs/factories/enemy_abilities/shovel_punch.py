from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.components.ability_target import AbilityTarget
from ecs.components.ability_cooldown import AbilityCooldown


def create_ability_shovel_punch(world: World) -> int:
    """Deal a straightforward hit to the opponent."""
    return world.create_entity(
        Ability(
            name="shovel_punch",
            kind="active",
            cost={"nature": 4, "shapeshift": 4},
            description="Deal 5 damage to the opponent.",
            cooldown=0,
        ),
        AbilityTarget(target_type="self", max_targets=0),
        AbilityEffects(
            effects=(
                AbilityEffectSpec(
                    slug="damage",
                    target="opponent",
                    turns=0,
                    metadata={
                        "amount": 5,
                        "reason": "shovel_punch",
                    },
                ),
            )
        ),
        AbilityCooldown(),
    )
