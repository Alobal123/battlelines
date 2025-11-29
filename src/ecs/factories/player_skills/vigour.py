from __future__ import annotations

from esper import World

from ecs.components.skill import Skill
from ecs.components.skill_effect import SkillEffectSpec, SkillEffects


def create_skill_vigour(world: World) -> int:
    """Create the Vigour passive skill entity."""

    return world.create_entity(
        Skill(
            name="Vigour",
            description=(
                "Whenever you heal for more than your maximum HP, deal the overflow as damage "
                "to the opposing combatant."
            ),
            tags=("nature", "healing", "retaliation"),
            affinity_bonus={"nature": 1},
        ),
        SkillEffects(
            effects=(
                SkillEffectSpec(
                    slug="vigour",
                    turns=None,
                    metadata={},
                ),
            ),
        ),
    )
