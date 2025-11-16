from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.components.ability_cooldown import AbilityCooldown


def create_ability_spirit_leech(world: World) -> int:
    """Create the Spirit Leech ability for draining opponent mana."""
    return world.create_entity(
        Ability(
            name="spirit_leech",
            kind="active",
            cost={"spirit": 4},
            description="Drain 2 mana from the opponent and deal 2 damage.",
            cooldown=1,
        ),
        AbilityTarget(target_type="self", max_targets=0),
        AbilityEffects(
            effects=(
                AbilityEffectSpec(
                    slug="mana_drain",
                    target="opponent",
                    turns=0,
                    metadata={
                        "amount": 2,
                        "mode": "random_eligible",
                        "reason": "spirit_leech",
                    },
                ),
                AbilityEffectSpec(
                    slug="damage",
                    target="opponent",
                    turns=0,
                    metadata={
                        "amount": 2,
                        "reason": "spirit_leech",
                    },
                ),
            )
        ),
        AbilityCooldown(),
    )
