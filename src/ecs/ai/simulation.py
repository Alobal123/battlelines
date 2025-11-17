from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from typing import Dict, Iterable, Tuple

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_cooldown import AbilityCooldown
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.ability_target import AbilityTarget
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.active_switch import ActiveSwitch
from ecs.components.active_turn import ActiveTurn
from ecs.components.board import Board
from ecs.components.board_position import BoardPosition
from ecs.components.human_agent import HumanAgent
from ecs.components.random_agent import RandomAgent
from ecs.components.tile import TileType
from ecs.components.tile_bank import TileBank
from ecs.components.tile_type_registry import TileTypeRegistry
from ecs.components.tile_types import TileTypes
from ecs.components.turn_state import TurnState
from ecs.events.bus import EventBus
from ecs.events.bus import EVENT_ABILITY_EXECUTE
from ecs.systems.ability_resolution_system import AbilityResolutionSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.board_clear_effect_system import BoardClearEffectSystem
from ecs.systems.effects.board_transform_effect_system import BoardTransformEffectSystem
from ecs.systems.board_ops import (
    clear_tiles_with_cascade,
    find_all_matches,
    predict_swap_creates_match,
    swap_tile_types,
)

BoardPositionType = Tuple[int, int]
TypeEntry = Tuple[int, int, str]
DEFAULT_COMPONENTS: Tuple[type, ...] = (
    Board,
    BoardPosition,
    TileType,
    ActiveSwitch,
    TileTypeRegistry,
    TileTypes,
    AbilityListOwner,
    Ability,
    AbilityTarget,
    AbilityCooldown,
    TileBank,
    ActiveTurn,
    TurnState,
    HumanAgent,
    RandomAgent,
)


@dataclass(slots=True)
class CloneState:
    """Container for cloned simulation state."""

    world: World
    event_bus: EventBus
    entity_map: Dict[int, int]
    engine: "SimulationEngine"


def clone_world_state(world: World, components: Iterable[type] | None = None) -> CloneState:
    """Create a lightweight cloned world containing only selected components.

    A fresh ``EventBus`` is created for the clone so that any future event-driven
    evaluation stays isolated from the live game's bus.
    """

    comps = tuple(components) if components is not None else DEFAULT_COMPONENTS
    clone = World()
    entity_map: Dict[int, int] = {}
    relevant_entities: set[int] = set()
    for comp_type in comps:
        for ent, _ in world.get_component(comp_type):
            relevant_entities.add(ent)
    for ent in relevant_entities:
        entity_map[ent] = clone.create_entity()
    for comp_type in comps:
        for ent, comp in world.get_component(comp_type):
            new_ent = entity_map[ent]
            new_comp = deepcopy(comp)
            if isinstance(new_comp, AbilityListOwner):
                new_comp.ability_entities = [
                    entity_map[a]
                    for a in new_comp.ability_entities
                    if a in entity_map
                ]
            elif isinstance(new_comp, TileBank):
                if new_comp.owner_entity in entity_map:
                    new_comp.owner_entity = entity_map[new_comp.owner_entity]
            elif isinstance(new_comp, ActiveTurn):
                if new_comp.owner_entity in entity_map:
                    new_comp.owner_entity = entity_map[new_comp.owner_entity]
            clone.add_component(new_ent, new_comp)
    event_bus = EventBus()
    engine = SimulationEngine(clone, event_bus)
    return CloneState(world=clone, event_bus=event_bus, entity_map=entity_map, engine=engine)


def _find_entity_at(world: World, position: BoardPositionType) -> int | None:
    row, col = position
    for ent, board_pos in world.get_component(BoardPosition):
        if board_pos.row == row and board_pos.col == col:
            return ent
    return None


class SimulationEngine:
    """Utility to execute real game logic inside a cloned world."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        # Ability resolution depends on lifecycle + board effect systems.
        self.effect_lifecycle = EffectLifecycleSystem(world, event_bus)
        self.board_clear_effect = BoardClearEffectSystem(world, event_bus, refill_cascades=False)
        self.board_transform_effect = BoardTransformEffectSystem(world, event_bus)
        self.ability_resolution = AbilityResolutionSystem(world, event_bus)
        self.last_action_generated_extra_turn: bool = False

    def swap_and_resolve(
        self,
        src: BoardPositionType,
        dst: BoardPositionType,
        *,
        acting_owner: int | None = None,
    ) -> None:
        """Perform a swap and resolve resulting cascades."""

        if not predict_swap_creates_match(self.world, src, dst):
            return
        if not swap_tile_types(self.world, src, dst):
            return
        self.last_action_generated_extra_turn = False
        self._resolve_cascades(owner_hint=acting_owner, allow_extra_turn=True)

    def execute_ability(
        self,
        ability_entity: int,
        owner_entity: int,
        pending: PendingAbilityTarget | None = None,
    ) -> None:
        """Run ability resolution end-to-end inside the clone."""

        if pending is not None:
            self.world.add_component(ability_entity, pending)
        self.event_bus.emit(
            EVENT_ABILITY_EXECUTE,
            ability_entity=ability_entity,
            owner_entity=owner_entity,
            pending=pending,
        )
        self.last_action_generated_extra_turn = False
        self._resolve_cascades(owner_hint=owner_entity, allow_extra_turn=False)

    def _resolve_cascades(self, owner_hint: int | None = None, *, allow_extra_turn: bool) -> None:
        while True:
            matches = find_all_matches(self.world)
            if not matches:
                break
            if allow_extra_turn and not self.last_action_generated_extra_turn:
                if any(len(group) >= 4 for group in matches):
                    self.last_action_generated_extra_turn = True
            positions = sorted({pos for group in matches for pos in group})
            _, typed_before, _, _, _ = clear_tiles_with_cascade(self.world, positions, refill=False)
            if typed_before:
                owner_entity = self._active_owner()
                if owner_entity is None:
                    owner_entity = owner_hint
                if owner_entity is not None:
                    self._apply_match_rewards(owner_entity, typed_before)

    def _active_owner(self) -> int | None:
        active_entries = list(self.world.get_component(ActiveTurn))
        if not active_entries:
            return None
        return active_entries[0][1].owner_entity

    def _apply_match_rewards(self, owner_entity: int, typed_entries: list[TypeEntry]) -> None:
        try:
            bank: TileBank = self.world.component_for_entity(owner_entity, TileBank)
        except KeyError:
            return
        gains: Dict[str, int] = {}
        for _, _, type_name in typed_entries:
            gains[type_name] = gains.get(type_name, 0) + 1
        for type_name, amount in gains.items():
            bank.add(type_name, amount)
