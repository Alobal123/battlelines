from __future__ import annotations

from typing import Any

from esper import World

from ecs.components.skill_list_owner import SkillListOwner
from ecs.components.starting_skill_choice import SkillChoice
from ecs.events.bus import EVENT_CHOICE_SELECTED, EVENT_SKILL_CHOICE_GRANTED, EventBus
from ecs.factories.skills import create_skill_by_name, skill_slugs_for_entity


class SkillChoiceSystem:
    """Grants skills when the player selects a skill choice option."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_CHOICE_SELECTED, self._on_choice_selected)

    def _on_choice_selected(self, sender: Any, **payload: Any) -> None:
        choice_entity = payload.get("choice_entity")
        if choice_entity is None:
            return
        try:
            choice = self.world.component_for_entity(choice_entity, SkillChoice)
        except KeyError:
            return
        owner = self._skill_owner(choice.owner_entity)
        if owner is None:
            return
        if self._owner_has_skill(owner, choice.skill_name):
            return
        skill_entity = create_skill_by_name(self.world, choice.skill_name)
        owner.skill_entities.append(skill_entity)
        self.event_bus.emit(
            EVENT_SKILL_CHOICE_GRANTED,
            owner_entity=choice.owner_entity,
            skill_entity=skill_entity,
            skill_name=choice.skill_name,
            choice_entity=choice_entity,
            window_entity=payload.get("window_entity"),
            press_id=payload.get("press_id"),
        )

    def _skill_owner(self, owner_entity: int) -> SkillListOwner | None:
        try:
            return self.world.component_for_entity(owner_entity, SkillListOwner)
        except KeyError:
            return None

    def _owner_has_skill(self, owner: SkillListOwner, skill_name: str) -> bool:
        if not skill_name:
            return False
        for skill_entity in list(owner.skill_entities):
            if skill_name in skill_slugs_for_entity(self.world, skill_entity):
                return True
        return False
