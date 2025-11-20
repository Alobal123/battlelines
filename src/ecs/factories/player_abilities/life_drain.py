from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.components.ability_cooldown import AbilityCooldown


def create_ability_life_drain(world: World) -> int:
    """Deal damage to the opponent and heal equal to the damage actually dealt."""

    return world.create_entity(
        Ability(
            name="life_drain",
            kind="active",
            cost={"blood": 7},
            description="Deal 2 damage to the opponent and heal for the damage actually dealt.",
            params={"damage_amount": 2},
            cooldown=1,
        ),
        AbilityTarget(target_type="self", max_targets=0),
        AbilityEffects(
            effects=(
                AbilityEffectSpec(
                    slug="damage",
                    target="opponent",
                    turns=0,
                    metadata={
                        "amount": 2,
                        "reason": "life_drain",
                        "context_write": "life_drain_damage",
                    },
                    param_overrides={"amount": "damage_amount"},
                ),
                AbilityEffectSpec(
                    slug="heal",
                    target="pending_target_or_self",
                    turns=0,
                    metadata={
                        "amount": 0,
                        "reason": "life_drain",
                        "context_read": {
                            "amount": "life_drain_damage",
                        },
                    },
                ),
            )
        ),
        AbilityCooldown(),
    )
