from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_cooldown import AbilityCooldown
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.components.ability_target import AbilityTarget


def create_ability_go_for_throat(world: World) -> int:
    """Lunge for the opponent's throat, dealing more damage for each Locked Scent."""
    return world.create_entity(
        Ability(
            name="go_for_throat",
            kind="active",
            cost={"shapeshift": 7},
            description="Deal 3 damage plus 2 for every Locked Scent on the target.",
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
                        "amount": 3,
                        "reason": "go_for_throat",
                        "context_read": {
                            "amount": "go_for_throat_damage",
                        },
                    },
                ),
            )
        ),
        AbilityCooldown(),
    )
