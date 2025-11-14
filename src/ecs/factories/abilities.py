from __future__ import annotations

from typing import List

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects


def create_default_player_abilities(world: World) -> List[int]:
    """Create the standard player ability loadout."""
    tactical_shift = world.create_entity(
        Ability(
            name="tactical_shift",
            kind="active",
            cost={"hex": 3, "nature": 2},
            description="Convert all tiles of the selected color to hex tiles.",
            params={"target_color": "hex"},
        ),
        AbilityTarget(target_type="tile", max_targets=1),
    )
    crimson_pulse = world.create_entity(
        Ability(
            name="crimson_pulse",
            kind="active",
            cost={"hex": 5},
            description="Clear a 3x3 area centered on the target tile.",
        ),
        AbilityTarget(target_type="tile", max_targets=1),
    )
    verdant_touch = world.create_entity(
        Ability(
            name="verdant_touch",
            kind="active",
            cost={"nature": 4},
            description="Heal 4 HP.",
            params={"heal_amount": 4},
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
    )
    blood_bolt = world.create_entity(
        Ability(
            name="blood_bolt",
            kind="active",
            cost={"blood": 4},
            description="Deal 2 damage to yourself and 6 damage to opponent.",
            params={"self_damage": 2, "opponent_damage": 6},
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
    )
    return [tactical_shift, crimson_pulse, verdant_touch, blood_bolt]
