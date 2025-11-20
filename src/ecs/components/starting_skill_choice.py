"""Components supporting the skill draft flow."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SkillChoice:
    """Marks a choice window option as a skill pick."""

    owner_entity: int
    skill_name: str
