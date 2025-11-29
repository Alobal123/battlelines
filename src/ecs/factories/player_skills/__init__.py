from __future__ import annotations

from ecs.factories.player_skills.self_reprimand import create_skill_self_reprimand
from ecs.factories.player_skills.void_tithe import create_skill_void_tithe
from ecs.factories.player_skills.blood_covenant import create_skill_blood_covenant
from ecs.factories.player_skills.vigour import create_skill_vigour

__all__ = [
    "create_skill_self_reprimand",
    "create_skill_void_tithe",
    "create_skill_blood_covenant",
    "create_skill_vigour",
]
