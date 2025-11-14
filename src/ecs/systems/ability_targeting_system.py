from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.ability_target import AbilityTarget
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.targeting_state import TargetingState
from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_ACTIVATE_REQUEST,
    EVENT_ABILITY_TARGET_CANCELLED,
    EVENT_ABILITY_TARGET_MODE,
    EVENT_ABILITY_TARGET_SELECTED,
    EVENT_MOUSE_PRESS,
    EVENT_TILE_BANK_SPEND_REQUEST,
    EVENT_TILE_CLICK,
)
from ecs.systems.turn_state_utils import get_or_create_turn_state


class AbilityTargetingSystem:
    """Handles ability activation and target selection flow."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        event_bus.subscribe(EVENT_ABILITY_ACTIVATE_REQUEST, self.on_activate_request)
        event_bus.subscribe(EVENT_TILE_CLICK, self.on_tile_click)
        event_bus.subscribe(EVENT_MOUSE_PRESS, self.on_mouse_press)

    def on_activate_request(self, sender, **payload) -> None:
        if self._is_cascade_active():
            return
        ability_entity = payload.get("ability_entity")
        owner_entity = payload.get("owner_entity")
        if ability_entity is None or owner_entity is None:
            return
        if not self._ability_belongs_to_owner(owner_entity, ability_entity):
            return
        if not self._is_owner_active(owner_entity):
            return
        
        # Check if ability needs targeting or can be executed immediately
        try:
            ability_target = self.world.component_for_entity(ability_entity, AbilityTarget)
            ability = self.world.component_for_entity(ability_entity, Ability)
        except KeyError:
            return
        
        # If target_type is "self", execute immediately without entering targeting mode
        if ability_target.target_type == "self":
            self.world.add_component(
                ability_entity,
                PendingAbilityTarget(
                    ability_entity=ability_entity,
                    owner_entity=owner_entity,
                    row=None,
                    col=None,
                    target_entity=owner_entity,  # Target is the caster
                ),
            )
            self.event_bus.emit(
                EVENT_TILE_BANK_SPEND_REQUEST,
                entity=owner_entity,
                cost=ability.cost,
                ability_entity=ability_entity,
            )
            return
        
        # Otherwise enter targeting mode
        self.world.add_component(owner_entity, TargetingState(ability_entity=ability_entity))
        self.event_bus.emit(
            EVENT_ABILITY_TARGET_MODE,
            ability_entity=ability_entity,
            owner_entity=owner_entity,
        )

    def on_tile_click(self, sender, **payload) -> None:
        if self._is_cascade_active():
            return
        targeting = list(self.world.get_component(TargetingState))
        if not targeting:
            return
        owner_entity, targeting_state = targeting[0]
        ability_entity = targeting_state.ability_entity
        if ability_entity is None:
            return
        try:
            ability_target = self.world.component_for_entity(ability_entity, AbilityTarget)
        except KeyError:
            return
        if ability_target.target_type != "tile":
            return
        row = payload.get("row")
        col = payload.get("col")
        if row is None or col is None:
            return
        try:
            ability = self.world.component_for_entity(ability_entity, Ability)
        except KeyError:
            return
        self.world.add_component(
            ability_entity,
            PendingAbilityTarget(
                ability_entity=ability_entity,
                owner_entity=owner_entity,
                row=row,
                col=col,
            ),
        )
        self.event_bus.emit(
            EVENT_TILE_BANK_SPEND_REQUEST,
            entity=owner_entity,
            cost=ability.cost,
            ability_entity=ability_entity,
        )
        self._clear_targeting(owner_entity)
        self.event_bus.emit(
            EVENT_ABILITY_TARGET_SELECTED,
            ability_entity=ability_entity,
            target=(row, col),
        )


    def on_mouse_press(self, sender, **payload) -> None:
        button = payload.get("button")
        if button != 4:
            return
        targeting = list(self.world.get_component(TargetingState))
        if not targeting:
            return
        owner_entity, targeting_state = targeting[0]
        ability_entity = targeting_state.ability_entity
        self._clear_targeting(owner_entity)
        self.event_bus.emit(
            EVENT_ABILITY_TARGET_CANCELLED,
            ability_entity=ability_entity,
            owner_entity=owner_entity,
            reason="right_click",
        )

    def _is_cascade_active(self) -> bool:
        state = get_or_create_turn_state(self.world)
        return state.cascade_active

    def _ability_belongs_to_owner(self, owner_entity: int, ability_entity: int) -> bool:
        for ent, owner_comp in self.world.get_component(AbilityListOwner):
            if ent == owner_entity and ability_entity in owner_comp.ability_entities:
                return True
        return False

    def _is_owner_active(self, owner_entity: int) -> bool:
        from ecs.components.active_turn import ActiveTurn

        active_turns = list(self.world.get_component(ActiveTurn))
        if not active_turns:
            return True
        return active_turns[0][1].owner_entity == owner_entity

    def _clear_targeting(self, owner_entity: int) -> None:
        try:
            self.world.remove_component(owner_entity, TargetingState)
        except KeyError:
            pass