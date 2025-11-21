from __future__ import annotations

from typing import Sequence

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.human_agent import HumanAgent
from ecs.components.skill import Skill
from ecs.components.skill_list_owner import SkillListOwner
from ecs.factories.abilities import create_ability_by_name
from ecs.factories.skills import create_skill_by_name


def grant_player_abilities(world: World, ability_names: Sequence[str]) -> list[int]:
    """Ensure the human player owns the specified abilities, creating them if needed."""

    if not ability_names:
        return []
    human_entities = list(world.get_component(HumanAgent))
    if not human_entities:
        return []
    owner_ent = human_entities[0][0]
    try:
        owner_comp = world.component_for_entity(owner_ent, AbilityListOwner)
    except KeyError:
        return []
    granted: list[int] = []
    for name in ability_names:
        if not name:
            continue
        ability_entity = None
        for candidate in owner_comp.ability_entities:
            try:
                ability = world.component_for_entity(candidate, Ability)
            except KeyError:
                continue
            if ability.name == name:
                ability_entity = candidate
                break
        if ability_entity is None:
            ability_entity = create_ability_by_name(world, name)
            owner_comp.ability_entities.append(ability_entity)
        granted.append(ability_entity)
    return granted


def grant_player_skills(world: World, skill_names: Sequence[str]) -> list[int]:
    """Ensure the human player owns the specified skills, creating them if needed."""

    if not skill_names:
        return []
    human_entities = list(world.get_component(HumanAgent))
    if not human_entities:
        return []
    owner_ent = human_entities[0][0]
    try:
        owner_comp = world.component_for_entity(owner_ent, SkillListOwner)
    except KeyError:
        return []
    granted: list[int] = []
    for name in skill_names:
        if not name:
            continue
        skill_entity = None
        for candidate in owner_comp.skill_entities:
            try:
                skill = world.component_for_entity(candidate, Skill)
            except KeyError:
                continue
            slug = skill.name.replace(" ", "_").lower() if skill.name else ""
            if slug == name:
                skill_entity = candidate
                break
        if skill_entity is None:
            skill_entity = create_skill_by_name(world, name)
            owner_comp.skill_entities.append(skill_entity)
        granted.append(skill_entity)
    return granted
