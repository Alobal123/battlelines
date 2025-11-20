from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.components.ability_cooldown import AbilityCooldown


def create_ability_blood_sacrifice(world: World) -> int:
    """Sacrifice a tile to convert its stored energy into blood mana."""

    return world.create_entity(
        Ability(
            name="blood_sacrifice",
            kind="active",
            cost={"blood": 7},
            description=(
                "Sacrifice a selected tile, gaining triple its effect while leaving the hole unfilled until a later cascade."
            ),
            cooldown=1,
        ),
        AbilityTarget(target_type="tile", max_targets=1),
        AbilityEffects(
            effects=(
                AbilityEffectSpec(
                    slug="tile_sacrifice",
                    target="board",
                    turns=0,
                    metadata={
                        "multiplier": 3,
                        "reason": "blood_sacrifice",
                        "refill": False,
                    },
                ),
            )
        ),
        AbilityCooldown(),
    )
