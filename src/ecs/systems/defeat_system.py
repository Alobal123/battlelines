from __future__ import annotations

import random
from typing import Callable, Iterable, Sequence

from esper import World

from ecs.components.ability_cooldown import AbilityCooldown
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.active_switch import ActiveSwitch
from ecs.components.active_turn import ActiveTurn
from ecs.components.board import Board
from ecs.components.board_position import BoardPosition
from ecs.components.effect_list import EffectList
from ecs.components.game_over_choice import GameOverChoice
from ecs.components.game_state import GameMode, GameState
from ecs.components.health import Health
from ecs.components.human_agent import HumanAgent
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.targeting_state import TargetingState
from ecs.components.tile import TileType
from ecs.components.tile_bank import TileBank
from ecs.components.turn_order import TurnOrder
from ecs.components.turn_state import TurnState
from ecs.events.bus import (
    EventBus,
    EVENT_CHOICE_SELECTED,
    EVENT_COMBAT_RESET,
    EVENT_ENEMY_DEFEATED,
    EVENT_ENTITY_DEFEATED,
    EVENT_EFFECT_REMOVE,
    EVENT_PLAYER_DEFEATED,
    EVENT_TILE_BANK_CHANGED,
)
from ecs.factories.choice_window import ChoiceDefinition, clear_choice_window, spawn_choice_window
from ecs.menu.components import MenuBackground, MenuButton, MenuTag
from ecs.menu.factory import spawn_main_menu
from ecs.systems.board_ops import get_tile_registry
from ecs.systems.turn_state_utils import get_or_create_turn_state
from ecs.utils.game_state import set_game_mode


class DefeatSystem:
    """Coordinates end-of-combat outcomes for player and enemy defeat events."""

    def __init__(
        self,
        world: World,
        event_bus: EventBus,
        *,
        menu_size_provider: Callable[[], tuple[float, float]] | None = None,
        menu_dimensions: tuple[float, float] | None = None,
    ) -> None:
        self.world = world
        self.event_bus = event_bus
        self._menu_size_provider = menu_size_provider
        self._menu_dimensions = menu_dimensions or (800.0, 600.0)
        self._game_over_window: int | None = None
        self._game_over_active = False
        self.event_bus.subscribe(EVENT_ENTITY_DEFEATED, self._on_entity_defeated)
        self.event_bus.subscribe(EVENT_CHOICE_SELECTED, self._on_choice_selected)

    def _on_entity_defeated(self, sender, **payload) -> None:
        entity = payload.get("entity")
        if entity is None:
            return
        if self._has_component(entity, HumanAgent):
            self._handle_player_defeat(entity)
        elif self._has_component(entity, RuleBasedAgent):
            self._handle_enemy_defeat(entity)

    def _on_choice_selected(self, sender, **payload) -> None:
        choice_entity = payload.get("choice_entity")
        if choice_entity is None:
            return
        try:
            choice = self.world.component_for_entity(choice_entity, GameOverChoice)
        except KeyError:
            return
        action = choice.action or "return_to_menu"
        if action == "return_to_menu":
            self._resolve_return_to_menu()

    def _handle_player_defeat(self, entity: int) -> None:
        if self._game_over_active:
            return
        self.event_bus.emit(EVENT_PLAYER_DEFEATED, entity=entity)
        self._game_over_active = True
        self._clear_transient_combat_state()
        clear_choice_window(self.world)
        description = "Return to the main menu."
        choices = (
            ChoiceDefinition(
                label="Return to Menu",
                description=description,
                components=(GameOverChoice(action="return_to_menu"),),
            ),
        )
        self._game_over_window = spawn_choice_window(
            self.world,
            choices,
            skippable=False,
            title="Defeat",
        )

    def _handle_enemy_defeat(self, entity: int) -> None:
        self.event_bus.emit(EVENT_ENEMY_DEFEATED, entity=entity)
        new_enemy = self._replace_enemy(entity)
        owners = self._owner_entities()
        self._reset_full_combat_state(
            owners,
            defeated_entity=entity,
            reason="enemy_defeated",
        )

    def _resolve_return_to_menu(self) -> None:
        owners = self._owner_entities()
        self._reset_full_combat_state(
            owners,
            defeated_entity=None,
            reason="player_defeated",
        )
        self._reset_player_abilities()
        self._set_game_mode(GameMode.MENU)
        self._clear_menu_entities()
        width, height = self._current_menu_dimensions()
        spawn_main_menu(self.world, int(width), int(height))
        self._game_over_active = False
        self._game_over_window = None

    def _reset_full_combat_state(
        self,
        owners: Sequence[int],
        *,
        defeated_entity: int | None,
        reason: str,
    ) -> None:
        self._clear_transient_combat_state()
        self._reset_tile_banks(owners)
        self._reset_effects(owners)
        self._reset_ability_cooldowns(owners)
        self._heal_owners(owners)
        self._reset_turn_structures(owners)
        self._reset_board()
        clear_choice_window(self.world)
        self._game_over_active = False
        self._game_over_window = None
        self.event_bus.emit(
            EVENT_COMBAT_RESET,
            reason=reason,
            defeated_entity=defeated_entity,
        )

    def _clear_transient_combat_state(self) -> None:
        self._clear_targeting_states()
        self._clear_pending_targets()
        self._clear_tooltips()

    def _owner_entities(self) -> list[int]:
        orders = list(self.world.get_component(TurnOrder))
        if orders:
            owners = list(orders[0][1].owners)
            if owners:
                return owners
        humans = [ent for ent, _ in self.world.get_component(HumanAgent)]
        others = [
            ent
            for ent, _ in self.world.get_component(AbilityListOwner)
            if ent not in humans
        ]
        humans.sort()
        others.sort()
        return humans + others

    def _reset_tile_banks(self, owners: Iterable[int]) -> None:
        owner_set = set(owners)
        for entity, bank in list(self.world.get_component(TileBank)):
            if owner_set and bank.owner_entity not in owner_set:
                continue
            if bank.counts:
                bank.counts.clear()
                self.event_bus.emit(
                    EVENT_TILE_BANK_CHANGED,
                    entity=entity,
                    counts=bank.counts.copy(),
                )

    def _reset_effects(self, owners: Iterable[int]) -> None:
        for owner in owners:
            self.event_bus.emit(
                EVENT_EFFECT_REMOVE,
                owner_entity=owner,
                remove_all=True,
            )
            try:
                effect_list = self.world.component_for_entity(owner, EffectList)
            except (KeyError, ValueError):
                continue
            for effect_entity in list(effect_list.effect_entities):
                self._delete_entity(effect_entity)
            effect_list.effect_entities.clear()

    def _reset_ability_cooldowns(self, owners: Iterable[int]) -> None:
        for owner in owners:
            for ability_entity in self._abilities_for_owner(owner):
                try:
                    cooldown = self.world.component_for_entity(ability_entity, AbilityCooldown)
                except (KeyError, ValueError):
                    continue
                cooldown.remaining_turns = 0

    def _heal_owners(self, owners: Iterable[int]) -> None:
        for owner in owners:
            try:
                health = self.world.component_for_entity(owner, Health)
            except (KeyError, ValueError):
                continue
            health.current = health.max_hp

    def _reset_turn_structures(self, owners: Sequence[int]) -> None:
        owners = list(owners)
        turn_orders = list(self.world.get_component(TurnOrder))
        if turn_orders:
            _, order = turn_orders[0]
            order.owners = owners
            order.index = 0
        elif owners:
            self.world.create_entity(TurnOrder(owners=list(owners), index=0))
        active_turns = list(self.world.get_component(ActiveTurn))
        if owners:
            first_owner = owners[0]
            if active_turns:
                _, active = active_turns[0]
                active.owner_entity = first_owner
            else:
                self.world.create_entity(ActiveTurn(owner_entity=first_owner))
        else:
            for ent, _ in active_turns:
                self._delete_entity(ent)
        turn_state: TurnState = get_or_create_turn_state(self.world)
        turn_state.action_source = None
        turn_state.cascade_active = False
        turn_state.cascade_depth = 0
        turn_state.cascade_observed = False
        turn_state.ability_entity = None
        turn_state.ability_ends_turn = True

    def _reset_board(self) -> None:
        board_entries = list(self.world.get_component(Board))
        if not board_entries:
            return
        _, board = board_entries[0]
        try:
            registry = get_tile_registry(self.world)
        except RuntimeError:
            return
        types = registry.all_types()
        if not types:
            return
        entity_grid: list[list[int | None]] = [
            [None for _ in range(board.cols)] for _ in range(board.rows)
        ]
        for ent, pos in self.world.get_component(BoardPosition):
            if 0 <= pos.row < board.rows and 0 <= pos.col < board.cols:
                entity_grid[pos.row][pos.col] = ent
        assigned: list[list[str | None]] = [
            [None for _ in range(board.cols)] for _ in range(board.rows)
        ]
        for row in range(board.rows):
            for col in range(board.cols):
                available = list(types)
                if col >= 2:
                    left1 = assigned[row][col - 1]
                    left2 = assigned[row][col - 2]
                    if left1 is not None and left1 == left2 and left1 in available:
                        available = [t for t in available if t != left1]
                if row >= 2:
                    up1 = assigned[row - 1][col]
                    up2 = assigned[row - 2][col]
                    if up1 is not None and up1 == up2 and up1 in available:
                        available = [t for t in available if t != up1]
                choice = random.choice(available or types)
                assigned[row][col] = choice
                entity = entity_grid[row][col]
                if entity is None:
                    continue
                try:
                    switch = self.world.component_for_entity(entity, ActiveSwitch)
                except (KeyError, ValueError):
                    switch = None
                if switch is not None:
                    switch.active = True
                try:
                    tile = self.world.component_for_entity(entity, TileType)
                except (KeyError, ValueError):
                    continue
                tile.type_name = choice

    def _clear_targeting_states(self) -> None:
        for entity, _ in list(self.world.get_component(TargetingState)):
            try:
                self.world.remove_component(entity, TargetingState)
            except KeyError:
                continue

    def _clear_pending_targets(self) -> None:
        for ability_entity, _ in list(self.world.get_component(PendingAbilityTarget)):
            try:
                self.world.remove_component(ability_entity, PendingAbilityTarget)
            except KeyError:
                continue

    def _clear_tooltips(self) -> None:
        try:
            from ecs.components.tooltip_state import TooltipState
        except ImportError:
            return
        entries = list(self.world.get_component(TooltipState))
        for _, tooltip in entries:
            tooltip.visible = False
            tooltip.lines = ()
            tooltip.width = 0.0
            tooltip.height = 0.0
            tooltip.target = ""
            tooltip.target_id = None

    def _reset_player_abilities(self) -> None:
        human_entities = [ent for ent, _ in self.world.get_component(HumanAgent)]
        for human in human_entities:
            try:
                owner = self.world.component_for_entity(human, AbilityListOwner)
            except (KeyError, ValueError):
                continue
            ability_entities = list(owner.ability_entities)
            owner.ability_entities.clear()
            for ability_entity in ability_entities:
                self._delete_entity(ability_entity)

    def _set_game_mode(self, mode: GameMode) -> None:
        set_game_mode(self.world, self.event_bus, mode)

    def _clear_menu_entities(self) -> None:
        targets = {
            *(ent for ent, _ in self.world.get_component(MenuTag)),
            *(ent for ent, _ in self.world.get_component(MenuButton)),
            *(ent for ent, _ in self.world.get_component(MenuBackground)),
        }
        for ent in targets:
            self._delete_entity(ent)

    def _current_menu_dimensions(self) -> tuple[float, float]:
        if self._menu_size_provider is not None:
            try:
                width, height = self._menu_size_provider()
                return float(width), float(height)
            except Exception:
                pass
        return self._menu_dimensions

    def _abilities_for_owner(self, owner_entity: int) -> Sequence[int]:
        try:
            owner = self.world.component_for_entity(owner_entity, AbilityListOwner)
        except (KeyError, ValueError):
            return ()
        return tuple(owner.ability_entities)

    def _delete_entity(self, entity: int) -> None:
        try:
            self.world.delete_entity(entity, immediate=True)
        except Exception:
            try:
                self.world.delete_entity(entity)
            except Exception:
                pass

    def _replace_enemy(self, defeated_entity: int) -> int | None:
        self._delete_entity(defeated_entity)
        enemy_pool = getattr(self.world, "enemy_pool", None)
        new_enemy: int | None = None
        if enemy_pool is not None:
            try:
                new_enemy = enemy_pool.spawn_random_enemy()
            except Exception:
                new_enemy = None
        if new_enemy is None:
            from ecs.factories.enemies import create_enemy_undead_gardener

            new_enemy = create_enemy_undead_gardener(self.world, max_hp=30)
        self._ensure_enemy_owner_order(new_enemy)
        self._replace_turn_order_owner(defeated_entity, new_enemy)
        self._replace_active_turn_owner(defeated_entity, new_enemy)
        return new_enemy

    def _ensure_enemy_owner_order(self, enemy_entity: int) -> None:
        try:
            abilities = self.world.component_for_entity(enemy_entity, AbilityListOwner)
        except (KeyError, ValueError):
            return
        self.world.remove_component(enemy_entity, AbilityListOwner)
        self.world.add_component(enemy_entity, abilities)

    def _replace_turn_order_owner(self, old_entity: int, new_entity: int) -> None:
        for _, order in self.world.get_component(TurnOrder):
            order.owners = [new_entity if ent == old_entity else ent for ent in order.owners]

    def _replace_active_turn_owner(self, old_entity: int, new_entity: int) -> None:
        for _, active in self.world.get_component(ActiveTurn):
            if active.owner_entity == old_entity:
                active.owner_entity = new_entity

    def _has_component(self, entity: int, component_type) -> bool:
        try:
            self.world.component_for_entity(entity, component_type)
            return True
        except (KeyError, ValueError):
            return False
