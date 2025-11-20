from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.components.ability_cooldown import AbilityCooldown


def create_ability_savagery(world: World) -> int:
    return world.create_entity(
        Ability(
            name="savagery",
            kind="active",
            cost={"shapeshift": 5},
            description="Gain +1 damage to all attacks for five turns.",
            cooldown=2,
            ends_turn=False,
        ),
        AbilityTarget(target_type="self", max_targets=0),
        AbilityEffects(
            effects=(
                AbilityEffectSpec(
                    slug="damage_bonus",
                    target="pending_target_or_self",
                    turns=5,
                    metadata={
                        "bonus": 1,
                        "reason": "savagery",
                        "stack_key": "damage_bonus",
                    },
                ),
            )
        ),
        AbilityCooldown(),
    )
