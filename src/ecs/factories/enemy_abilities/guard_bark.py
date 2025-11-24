from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_cooldown import AbilityCooldown
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.components.ability_target import AbilityTarget


def create_ability_guard_bark(world: World) -> int:
    """Bellow a warding bark that disrupts witchfire and mends wounds."""
    return world.create_entity(
        Ability(
            name="guard_bark",
            kind="active",
            cost={"shapeshift": 4},
            description="Convert up to three witchfire tiles into random mana and heal 3.",
            cooldown=0,
        ),
        AbilityTarget(target_type="self", max_targets=0),
        AbilityEffects(
            effects=(
                AbilityEffectSpec(
                    slug="board_transform_type",
                    target="board",
                    turns=0,
                    metadata={
                        "positions": [],
                        "target_types": [],
                        "reason": "guard_bark",
                        "emit_match_cleared": False,
                        "context_read": {
                            "positions": "guard_bark_positions",
                            "target_types": "guard_bark_target_types",
                        },
                    },
                ),
                AbilityEffectSpec(
                    slug="heal",
                    target="self",
                    turns=0,
                    metadata={
                        "amount": 3,
                        "reason": "guard_bark",
                    },
                ),
            )
        ),
        AbilityCooldown(),
    )
