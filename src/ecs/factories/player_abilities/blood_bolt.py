from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.components.ability_cooldown import AbilityCooldown


def create_ability_blood_bolt(world: World) -> int:
    return world.create_entity(
        Ability(
            name="blood_bolt",
            kind="active",
            cost={"blood": 4},
            description="Deal 2 damage to yourself and 6 damage to opponent.",
            params={"self_damage": 2, "opponent_damage": 6},
            cooldown=1,
        ),
        AbilityTarget(target_type="self", max_targets=0),
        AbilityEffects(
            effects=(
                AbilityEffectSpec(
                    slug="damage",
                    target="self",
                    turns=0,
                    metadata={
                        "amount": 2,
                        "reason": "blood_bolt_self",
                    },
                    param_overrides={"amount": "self_damage"},
                ),
                AbilityEffectSpec(
                    slug="damage",
                    target="opponent",
                    turns=0,
                    metadata={
                        "amount": 6,
                        "reason": "blood_bolt",
                    },
                    param_overrides={"amount": "opponent_damage"},
                ),
            )
        ),
        AbilityCooldown(),
    )
