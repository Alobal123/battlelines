from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.components.ability_target import AbilityTarget
from ecs.components.ability_cooldown import AbilityCooldown


def create_ability_touch_of_undead(world: World) -> int:
    """Drain mana from the opponent's tile bank and deal damage equal to the amount drained."""
    return world.create_entity(
        Ability(
            name="touch_of_undead",
            kind="active",
            cost={"spirit": 5},
            description="Drain 1 mana of each type from the opponent and deal damage equal to the drain.",
            cooldown=0,
        ),
        AbilityTarget(target_type="self", max_targets=0),
        AbilityEffects(
            effects=(
                AbilityEffectSpec(
                    slug="deplete",
                    target="opponent",
                    turns=0,
                    metadata={
                        "amount": 1,
                        "mode": "all",
                        "reason": "touch_of_undead",
                        "context_write": "touch_of_undead_total",
                        "context_write_map": "touch_of_undead_deltas",
                    },
                ),
                AbilityEffectSpec(
                    slug="damage",
                    target="opponent",
                    turns=0,
                    metadata={
                        "amount": 0,
                        "reason": "touch_of_undead",
                        "context_read": {
                            "amount": "touch_of_undead_total",
                        },
                    },
                ),
            )
        ),
        AbilityCooldown(),
    )
