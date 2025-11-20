from __future__ import annotations

from esper import World

from ecs.components.skill import Skill
from ecs.components.skill_effect import SkillEffectSpec, SkillEffects


def create_skill_blood_covenant(world: World) -> int:
    """Create the Blood Covenant passive skill entity."""

    return world.create_entity(
        Skill(
            name="Blood Covenant",
            description="At the start of your turn, deal one damage to yourself.",
            tags=("blood", "reckless"),
        ),
        SkillEffects(
            effects=(
                SkillEffectSpec(
                    slug="blood_covenant",
                    turns=None,
                    metadata={},
                ),
            ),
        ),
    )
