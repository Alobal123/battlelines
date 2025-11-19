from __future__ import annotations

from typing import Any

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.starting_ability_choice import AbilityChoice
from ecs.events.bus import EVENT_CHOICE_SELECTED, EVENT_ABILITY_CHOICE_GRANTED, EventBus
from ecs.factories.abilities import create_ability_by_name


class AbilityChoiceSystem:
    """Grants abilities when the player selects an ability choice option."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_CHOICE_SELECTED, self._on_choice_selected)

    def _on_choice_selected(self, sender: Any, **payload: Any) -> None:
        choice_entity = payload.get("choice_entity")
        if choice_entity is None:
            return
        try:
            choice = self.world.component_for_entity(choice_entity, AbilityChoice)
        except KeyError:
            return
        owner = self._ability_owner(choice.owner_entity)
        if owner is None:
            return
        if self._owner_has_ability(owner, choice.owner_entity, choice.ability_name):
            return
        ability_entity = create_ability_by_name(self.world, choice.ability_name)
        owner.ability_entities.append(ability_entity)
        self.event_bus.emit(
            EVENT_ABILITY_CHOICE_GRANTED,
            owner_entity=choice.owner_entity,
            ability_entity=ability_entity,
            ability_name=choice.ability_name,
            choice_entity=choice_entity,
            window_entity=payload.get("window_entity"),
            press_id=payload.get("press_id"),
        )

    def _ability_owner(self, owner_entity: int) -> AbilityListOwner | None:
        try:
            return self.world.component_for_entity(owner_entity, AbilityListOwner)
        except KeyError:
            return None

    def _owner_has_ability(self, owner: AbilityListOwner, owner_entity: int, ability_name: str) -> bool:
        if not ability_name:
            return False
        for ability_entity in list(owner.ability_entities):
            try:
                ability = self.world.component_for_entity(ability_entity, Ability)
            except KeyError:
                continue
            if ability.name == ability_name:
                return True
        return False
