from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_cooldown import AbilityCooldown
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.components.ability_target import AbilityTarget


def create_ability_scent_lock(world: World) -> int:
    """Mark the opponent with a vicious bite that causes bleeding."""
    return world.create_entity(
        Ability(
            name="scent_lock",
            kind="active",
            cost={"blood": 2, "shapeshift": 2},
            description="Inflict heavy bleeding on the foe to set up the kill.",
            cooldown=1,
            ends_turn=False,
        ),
        AbilityTarget(target_type="self", max_targets=0),
        AbilityEffects(
            effects=(
                AbilityEffectSpec(
                    slug="bleeding",
                    target="opponent",
                    metadata={
                        "count": 5,
                        "reason": "scent_lock",
                    },
                ),
            )
        ),
        AbilityCooldown(),
    )
