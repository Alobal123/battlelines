from __future__ import annotations

from esper import World

from ecs.components.skill import Skill
from ecs.components.skill_effect import SkillEffectSpec, SkillEffects


def create_skill_self_reprimand(world: World) -> int:
    """Provide the self reprimand passive skill entity."""

    return world.create_entity(
        Skill(
            name="Self Reprimand",
            description="When you damage yourself, deal 1 damage and gain 1 blood.",
            tags=("blood", "retaliation"),
            affinity_bonus={"blood": 1},
        ),
        SkillEffects(
            effects=(
                SkillEffectSpec(
                    slug="self_reprimand",
                    turns=None,
                    metadata={},
                ),
            ),
        ),
    )
