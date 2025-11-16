from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.components.ability_cooldown import AbilityCooldown


def create_ability_verdant_touch(world: World) -> int:
    return world.create_entity(
        Ability(
            name="verdant_touch",
            kind="active",
            cost={"nature": 4},
            description="Heal 4 HP.",
            params={"heal_amount": 4},
            cooldown=1,
        ),
        AbilityTarget(target_type="self", max_targets=0),
        AbilityEffects(
            effects=(
                AbilityEffectSpec(
                    slug="heal",
                    target="pending_target_or_self",
                    turns=0,
                    metadata={
                        "amount": 4,
                        "reason": "verdant_touch",
                    },
                    param_overrides={"amount": "heal_amount"},
                ),
            )
        ),
        AbilityCooldown(),
    )
