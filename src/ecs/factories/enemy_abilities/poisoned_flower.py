from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_cooldown import AbilityCooldown
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.components.ability_target import AbilityTarget


def create_ability_poisoned_flower(world: World) -> int:
    """Apply a lingering poison that chips away at the opponent over time."""
    return world.create_entity(
        Ability(
            name="poisoned_flower",
            kind="active",
            cost={"nature": 5, "hex": 3},
            description="Inflict 6 poison (1 damage per turn) on the opponent.",
            cooldown=0,
        ),
        AbilityTarget(target_type="self", max_targets=0),
        AbilityEffects(
            effects=(
                AbilityEffectSpec(
                    slug="poison",
                    target="opponent",
                    turns=None,
                    metadata={
                        "count": 6,
                        "reason": "poison",
                        "source_owner": None,
                    },
                ),
            )
        ),
        AbilityCooldown(),
    )
