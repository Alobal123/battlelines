from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_cooldown import AbilityCooldown
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_EXECUTE,
    EVENT_TURN_ADVANCED,
)


class AbilityCooldownSystem:
    """Maintains per-ability cooldown timers and resets them on use."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        event_bus.subscribe(EVENT_ABILITY_EXECUTE, self.on_ability_execute)
        event_bus.subscribe(EVENT_TURN_ADVANCED, self.on_turn_advanced)

    def on_ability_execute(self, sender, **payload) -> None:
        ability_entity = payload.get("ability_entity")
        if ability_entity is None:
            return
        ability = self._get_ability(ability_entity)
        if ability is None:
            return
        state = self._ensure_state(ability_entity)
        state.remaining_turns = max(0, int(ability.cooldown))

    def on_turn_advanced(self, sender, **payload) -> None:
        owner_to_tick = payload.get("new_owner")
        if owner_to_tick is None:
            owner_to_tick = payload.get("previous_owner")
        if owner_to_tick is None:
            return
        for ability_entity in self._abilities_for_owner(owner_to_tick):
            try:
                state = self.world.component_for_entity(ability_entity, AbilityCooldown)
            except KeyError:
                continue
            if state.remaining_turns > 0:
                state.remaining_turns = max(0, state.remaining_turns - 1)

    def _ensure_state(self, ability_entity: int) -> AbilityCooldown:
        try:
            return self.world.component_for_entity(ability_entity, AbilityCooldown)
        except KeyError:
            state = AbilityCooldown()
            self.world.add_component(ability_entity, state)
            return state

    def _get_ability(self, ability_entity: int) -> Ability | None:
        try:
            return self.world.component_for_entity(ability_entity, Ability)
        except KeyError:
            return None

    def _abilities_for_owner(self, owner_entity: int) -> list[int]:
        for ent, owner_comp in self.world.get_component(AbilityListOwner):
            if ent == owner_entity:
                return list(owner_comp.ability_entities)
        return []
