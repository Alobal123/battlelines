from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_cooldown import AbilityCooldown
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.components.ability_target import AbilityTarget


def create_ability_bee_sting(world: World) -> int:
    """Deal damage equal to the number of nature tiles currently on the board."""
    return world.create_entity(
        Ability(
            name="bee_sting",
            kind="active",
            cost={"nature": 3, "spirit": 3, "shapeshift": 3},
            description="Sting the foe, dealing damage equal to all nature tiles on the board.",
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
                        "amount": 0,
                        "reason": "bee_sting",
                        "context_read": {
                            "amount": "bee_sting_amount",
                        },
                    },
                ),
            )
        ),
        AbilityCooldown(),
    )
