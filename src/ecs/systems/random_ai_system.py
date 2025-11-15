from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Tuple, cast

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_cooldown import AbilityCooldown
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.ability_target import AbilityTarget
from ecs.components.random_agent import RandomAgent
from ecs.components.targeting_state import TargetingState
from ecs.components.tile_bank import TileBank
from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_ACTIVATE_REQUEST,
    EVENT_TILE_CLICK,
    EVENT_TILE_SWAP_REQUEST,
    EVENT_TICK,
    EVENT_TURN_ACTION_STARTED,
    EVENT_TURN_ADVANCED,
)
from ecs.systems.board_ops import active_tile_type_map, find_valid_swaps
from ecs.systems.turn_state_utils import get_or_create_turn_state

Position = Tuple[int, int]


@dataclass(slots=True)
class AbilityAction:
    ability_entity: int
    target_type: str
    target: Optional[Position] = None


ActionPayload = Tuple[Position, Position] | AbilityAction


class RandomAISystem:
    """Issues random valid actions for entities marked with RandomAgent."""

    def __init__(
        self,
        world: World,
        event_bus: EventBus,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.world = world
        self.event_bus = event_bus
        self.random = rng or random.Random()
        self.pending_owner: Optional[int] = None
        self.has_dispatched_action = False
        self.delay_remaining: float = 0.0
        self.current_action: Optional[Tuple[str, ActionPayload]] = None
        self.action_phase: Optional[str] = None
        event_bus.subscribe(EVENT_TURN_ADVANCED, self.on_turn_advanced)
        event_bus.subscribe(EVENT_TURN_ACTION_STARTED, self.on_turn_action_started)
        event_bus.subscribe(EVENT_TICK, self.on_tick)
        self._prime_initial_owner()

    def on_turn_advanced(self, sender, **payload) -> None:
        new_owner = payload.get("new_owner")
        if new_owner is not None and self._is_ai_owner(new_owner):
            self.pending_owner = new_owner
            self.has_dispatched_action = False
            self.delay_remaining = self._decision_delay_for(new_owner)
            self.current_action = None
            self.action_phase = None
        else:
            self.pending_owner = None
            self.has_dispatched_action = False
            self.delay_remaining = 0.0
            self.current_action = None
            self.action_phase = None

    def on_turn_action_started(self, sender, **payload) -> None:
        owner_entity = payload.get("owner_entity")
        if owner_entity is not None and self._is_ai_owner(owner_entity):
            self.pending_owner = None
            self.has_dispatched_action = True
            self.delay_remaining = 0.0
            self.current_action = None
            self.action_phase = None

    def on_tick(self, sender, **payload) -> None:
        if self.pending_owner is None or self.has_dispatched_action:
            return
        if self._is_cascade_active():
            return
        if self.current_action is None and self._has_pending_targeting():
            return
        dt = float(payload.get("dt", 0.0))
        if self.delay_remaining > 0.0:
            self.delay_remaining = max(0.0, self.delay_remaining - dt)
            if self.delay_remaining > 0.0:
                return
        if self.current_action is None:
            action = self._choose_action(self.pending_owner)
            if action is None:
                self.has_dispatched_action = True
                return
            self.current_action = action
            kind, _ = action
            self.action_phase = "start"
        self._progress_action()

    def _choose_action(self, owner_entity: int) -> Optional[Tuple[str, ActionPayload]]:
        swaps = find_valid_swaps(self.world)
        candidates: List[Tuple[str, ActionPayload]] = []
        for swap in swaps:
            candidates.append(("swap", swap))
        for ability_action in self._enumerate_ability_actions(owner_entity):
            candidates.append(("ability", ability_action))
        if not candidates:
            return None
        return self.random.choice(candidates)

    def _progress_action(self) -> None:
        if self.current_action is None or self.pending_owner is None:
            return
        kind, payload_obj = self.current_action
        if kind == "swap":
            src, dst = cast(Tuple[Position, Position], payload_obj)
            if self.action_phase == "start":
                self.event_bus.emit(EVENT_TILE_CLICK, row=src[0], col=src[1])
                self.action_phase = "swap_target"
                self.delay_remaining = self._selection_delay_for(self.pending_owner)
                if self.delay_remaining <= 0.0:
                    self._progress_action()
                return
            if self.action_phase == "swap_target":
                self.event_bus.emit(EVENT_TILE_CLICK, row=dst[0], col=dst[1])
                self._complete_action()
                return
        elif kind == "ability":
            ability_action = cast(AbilityAction, payload_obj)
            if self.action_phase == "start":
                self.event_bus.emit(
                    EVENT_ABILITY_ACTIVATE_REQUEST,
                    ability_entity=ability_action.ability_entity,
                    owner_entity=self.pending_owner,
                )
                if ability_action.target_type == "tile" and ability_action.target is not None:
                    self.action_phase = "ability_target"
                    self.delay_remaining = self._selection_delay_for(self.pending_owner)
                    if self.delay_remaining <= 0.0:
                        self._progress_action()
                    return
                self._complete_action()
                return
            if (
                self.action_phase == "ability_target"
                and ability_action.target_type == "tile"
                and ability_action.target is not None
            ):
                row, col = ability_action.target
                self.event_bus.emit(EVENT_TILE_CLICK, row=row, col=col)
                self._complete_action()

    def _complete_action(self) -> None:
        self.current_action = None
        self.action_phase = None
        self.delay_remaining = 0.0
        self.has_dispatched_action = True

    def _enumerate_ability_actions(self, owner_entity: int) -> List[AbilityAction]:
        try:
            owner_comp: AbilityListOwner = self.world.component_for_entity(
                owner_entity, AbilityListOwner
            )
        except KeyError:
            return []
        try:
            bank: TileBank | None = self.world.component_for_entity(owner_entity, TileBank)
        except KeyError:
            bank = None
        tile_positions = active_tile_type_map(self.world)
        actions: List[AbilityAction] = []
        for ability_entity in owner_comp.ability_entities:
            try:
                ability: Ability = self.world.component_for_entity(ability_entity, Ability)
            except KeyError:
                continue
            if bank is not None and ability.cost and not bank.can_spend(ability.cost):
                continue
            try:
                cooldown: AbilityCooldown = self.world.component_for_entity(
                    ability_entity, AbilityCooldown
                )
                if cooldown.remaining_turns > 0:
                    continue
            except KeyError:
                pass
            target_type = "self"
            target = None
            try:
                ability_target: AbilityTarget = self.world.component_for_entity(
                    ability_entity, AbilityTarget
                )
                target_type = ability_target.target_type
            except KeyError:
                target_type = "self"
            if target_type == "self":
                actions.append(AbilityAction(ability_entity=ability_entity, target_type="self"))
            elif target_type == "tile":
                if not tile_positions:
                    continue
                for pos in tile_positions.keys():
                    actions.append(
                        AbilityAction(
                            ability_entity=ability_entity,
                            target_type="tile",
                            target=pos,
                        )
                    )
        return actions

    def _is_cascade_active(self) -> bool:
        state = get_or_create_turn_state(self.world)
        return state.cascade_active

    def _has_pending_targeting(self) -> bool:
        states = list(self.world.get_component(TargetingState))
        return bool(states)

    def _is_ai_owner(self, owner_entity: int) -> bool:
        try:
            self.world.component_for_entity(owner_entity, RandomAgent)
            return True
        except KeyError:
            return False

    def _decision_delay_for(self, owner_entity: int) -> float:
        try:
            agent: RandomAgent = self.world.component_for_entity(owner_entity, RandomAgent)
            return max(0.0, agent.decision_delay)
        except KeyError:
            return 0.0

    def _selection_delay_for(self, owner_entity: int) -> float:
        try:
            agent: RandomAgent = self.world.component_for_entity(owner_entity, RandomAgent)
            return max(0.0, agent.selection_delay)
        except KeyError:
            return 0.0

    def _prime_initial_owner(self) -> None:
        from ecs.components.active_turn import ActiveTurn

        active_entries = list(self.world.get_component(ActiveTurn))
        if not active_entries:
            return
        _, active = active_entries[0]
        if self._is_ai_owner(active.owner_entity):
            self.pending_owner = active.owner_entity
            self.has_dispatched_action = False
            self.delay_remaining = self._decision_delay_for(active.owner_entity)
            self.current_action = None
            self.action_phase = None

