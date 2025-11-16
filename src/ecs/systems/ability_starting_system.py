"""System handling the player's initial ability selection."""
from __future__ import annotations

from typing import Callable, Optional

from esper import World

from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.game_state import GameMode, GameState
from ecs.components.starting_ability_choice import StartingAbilityChoice
from ecs.events.bus import EVENT_CHOICE_SELECTED, EventBus
from ecs.factories.abilities import create_ability_by_name
from ecs.factories.choice_window import clear_choice_window


class AbilityStartingSystem:
    def __init__(
        self,
        world: World,
        event_bus: EventBus,
        on_selection_complete: Optional[Callable[[], None]] = None,
    ) -> None:
        self.world = world
        self.event_bus = event_bus
        self._on_selection_complete = on_selection_complete
        self.event_bus.subscribe(EVENT_CHOICE_SELECTED, self._on_choice_selected)

    def _on_choice_selected(self, sender, **payload) -> None:
        choice_entity = payload.get("choice_entity")
        if choice_entity is None:
            return
        try:
            choice = self.world.component_for_entity(choice_entity, StartingAbilityChoice)
        except KeyError:
            return
        ability_entity = create_ability_by_name(self.world, choice.ability_name)
        try:
            owner_comp = self.world.component_for_entity(choice.owner_entity, AbilityListOwner)
        except KeyError:
            clear_choice_window(self.world)
            return
        if ability_entity not in owner_comp.ability_entities:
            owner_comp.ability_entities.append(ability_entity)
        state_entries = list(self.world.get_component(GameState))
        if state_entries:
            state_entries[0][1].mode = GameMode.COMBAT
        if self._on_selection_complete is not None:
            self._on_selection_complete()
        clear_choice_window(self.world)
