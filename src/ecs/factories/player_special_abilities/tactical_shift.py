from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.components.ability_cooldown import AbilityCooldown


def create_ability_tactical_shift(world: World) -> int:
    return world.create_entity(
        Ability(
            name="tactical_shift",
            kind="active",
            cost={"hex": 3, "nature": 2},
            description="Convert all tiles of the selected color to hex tiles.",
            params={"target_color": "hex"},
            cooldown=1,
        ),
        AbilityTarget(target_type="tile", max_targets=1),
        AbilityEffects(
            effects=(
                AbilityEffectSpec(
                    slug="board_transform_type",
                    target="board",
                    metadata={
                        "target_type": "hex",
                        "reason": "tactical_shift",
                    },
                    param_overrides={"target_type": "target_color"},
                ),
            )
        ),
        AbilityCooldown(),
    )
