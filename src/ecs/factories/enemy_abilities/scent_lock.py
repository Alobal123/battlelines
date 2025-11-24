from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_cooldown import AbilityCooldown
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.components.ability_target import AbilityTarget


def create_ability_scent_lock(world: World) -> int:
    """Mark the opponent with a lingering scent."""
    return world.create_entity(
        Ability(
            name="scent_lock",
            kind="active",
            cost={"blood": 2, "shapeshift": 2},
            description="Mark the foe with a lingering scent for several turns.",
            cooldown=1,
            ends_turn=False,
        ),
        AbilityTarget(target_type="self", max_targets=0),
        AbilityEffects(
            effects=(
                AbilityEffectSpec(
                    slug="locked_scent",
                    target="opponent",
                    turns=5,
                ),
            )
        ),
        AbilityCooldown(),
    )
