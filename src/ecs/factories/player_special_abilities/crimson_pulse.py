from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.components.ability_cooldown import AbilityCooldown


def create_ability_crimson_pulse(world: World) -> int:
    return world.create_entity(
        Ability(
            name="crimson_pulse",
            kind="active",
            cost={"hex": 5},
            description="Clear a 3x3 area centered on the target tile.",
            cooldown=2,
        ),
        AbilityTarget(target_type="tile", max_targets=1),
        AbilityEffects(
            effects=(
                AbilityEffectSpec(
                    slug="board_clear_area",
                    target="board",
                    metadata={
                        "shape": "square",
                        "radius": 1,
                        "reason": "crimson_pulse",
                        "source": "ability",
                    },
                ),
            )
        ),
        AbilityCooldown(),
    )
