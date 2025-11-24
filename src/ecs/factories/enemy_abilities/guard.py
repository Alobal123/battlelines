from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_cooldown import AbilityCooldown
from ecs.components.ability_target import AbilityTarget


def create_ability_guard(world: World) -> int:
    """Set defensive wards on random tiles, punishing intruders."""
    return world.create_entity(
        Ability(
            name="guard",
            kind="active",
            cost={"spirit": 3, "shapeshift": 3},
            description="Place up to five guarded tiles that retaliate when cleared.",
            cooldown=0,
        ),
        AbilityTarget(target_type="self", max_targets=0),
        AbilityCooldown(),
    )
