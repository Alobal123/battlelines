"""System handling the player's initial ability selection."""
from __future__ import annotations

from typing import Callable, Optional

from esper import World

from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.game_state import GameMode
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.starting_ability_choice import StartingAbilityChoice
from ecs.events.bus import EVENT_CHOICE_SELECTED, EVENT_DIALOGUE_START, EventBus
from ecs.factories.abilities import create_ability_by_name
from ecs.factories.choice_window import clear_choice_window
from ecs.utils.game_state import set_game_mode


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
        enemy_entity = self._find_enemy_entity(choice.owner_entity)
        if enemy_entity is not None:
            set_game_mode(self.world, self.event_bus, GameMode.DIALOGUE)
            self.event_bus.emit(
                EVENT_DIALOGUE_START,
                left_entity=choice.owner_entity,
                right_entity=enemy_entity,
                resume_mode=GameMode.COMBAT,
            )
        else:
            set_game_mode(self.world, self.event_bus, GameMode.COMBAT)
        if self._on_selection_complete is not None:
            self._on_selection_complete()
        clear_choice_window(self.world)

    def _find_enemy_entity(self, owner_entity: int) -> int | None:
        candidates = [ent for ent, _ in self.world.get_component(RuleBasedAgent)]
        if not candidates:
            return None
        # Prefer a non-player entity that isn't the owner.
        for entity in candidates:
            if entity != owner_entity:
                return entity
        return candidates[0]
