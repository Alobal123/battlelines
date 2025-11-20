from __future__ import annotations

from esper import World

from ecs.components.skill import Skill
from ecs.components.skill_effect import SkillEffectSpec, SkillEffects


def create_skill_void_tithe(world: World) -> int:
    """Create the Void Tithe passive skill entity."""

    return world.create_entity(
        Skill(
            name="Void Tithe",
            description="At the end of your turn, deal damage equal to your empty board tiles.",
            tags=("void", "retaliation"),
        ),
        SkillEffects(
            effects=(
                SkillEffectSpec(
                    slug="void_tithe",
                    turns=None,
                    metadata={},
                ),
            ),
        ),
    )
