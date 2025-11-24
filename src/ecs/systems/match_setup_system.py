"""Systems handling opponent selection and match flow transitions."""
from __future__ import annotations

import random
from typing import Callable

from esper import World

from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.active_turn import ActiveTurn
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.turn_order import TurnOrder
from ecs.components.game_state import GameMode
from ecs.events.bus import (
    EVENT_MATCH_READY,
    EVENT_MATCH_SETUP_REQUEST,
    EventBus,
)
from ecs.utils.combatants import ensure_combatants


FlowCallback = Callable[[], None]


class MatchSetupSystem:
    """Coordinates opponent selection and dialogue kick-off after ability grants."""

    def __init__(
        self,
        world: World,
        event_bus: EventBus,
        *,
        rng: random.Random | None = None,
        enemy_pool: object | None = None,
        dialogue_mode: GameMode = GameMode.DIALOGUE,
        resume_mode: GameMode = GameMode.COMBAT,
        fallback_mode: GameMode = GameMode.COMBAT,
        on_setup_complete: FlowCallback | None = None,
    ) -> None:
        self.world = world
        self.event_bus = event_bus
        self._rng = rng or getattr(world, "random", None) or random.SystemRandom()
        self._enemy_pool = enemy_pool or getattr(world, "enemy_pool", None)
        self._dialogue_mode = dialogue_mode
        self._resume_mode = resume_mode
        self._fallback_mode = fallback_mode
        self._on_setup_complete = on_setup_complete
        self.event_bus.subscribe(EVENT_MATCH_SETUP_REQUEST, self._on_match_setup_request)

    def _on_match_setup_request(self, sender, **payload) -> None:
        owner_entity = payload.get("owner_entity")
        if owner_entity is None:
            owner_entity = self._default_owner_entity()
        if owner_entity is None:
            return
        enemy_entity = payload.get("enemy_entity")
        if enemy_entity is None:
            enemy_entity = self._pick_existing_enemy(owner_entity)
        if enemy_entity is None:
            enemy_entity = self._spawn_enemy()
        self._emit_match_ready(
            owner_entity,
            enemy_entity,
            press_id=payload.get("press_id"),
            reason=payload.get("reason"),
            location_slug=payload.get("location_slug"),
        )

    def _prepare_primary_combatants(self, owner_entity: int, enemy_entity: int) -> None:
        ensure_combatants(self.world, owner_entity, enemy_entity)
        self._prune_extra_enemies(enemy_entity)
        self._ensure_enemy_component_order(enemy_entity)
        self._sync_turn_structures(owner_entity, enemy_entity)

    def _emit_match_ready(
        self,
        owner_entity: int,
        enemy_entity: int | None,
        *,
        press_id: int | None,
        reason: str | None = None,
        location_slug: str | None = None,
    ) -> None:
        if enemy_entity is not None:
            self._prepare_primary_combatants(owner_entity, enemy_entity)
        self.event_bus.emit(
            EVENT_MATCH_READY,
            owner_entity=owner_entity,
            enemy_entity=enemy_entity,
            press_id=press_id,
            reason=reason,
            location_slug=location_slug,
            dialogue_mode=self._dialogue_mode,
            resume_mode=self._resume_mode,
            fallback_mode=self._fallback_mode,
        )
        if self._on_setup_complete is not None:
            self._on_setup_complete()

    def _prune_extra_enemies(self, active_enemy: int) -> None:
        for entity, _ in list(self.world.get_component(RuleBasedAgent)):
            if entity == active_enemy:
                continue
            self._delete_entity(entity)

    def _ensure_enemy_component_order(self, enemy_entity: int) -> None:
        try:
            abilities = self.world.component_for_entity(enemy_entity, AbilityListOwner)
        except (KeyError, ValueError):
            return
        self.world.remove_component(enemy_entity, AbilityListOwner)
        self.world.add_component(enemy_entity, abilities)

    def _sync_turn_structures(self, owner_entity: int, enemy_entity: int) -> None:
        owners: list[int] = [owner_entity]
        if enemy_entity != owner_entity:
            owners.append(enemy_entity)
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

    def _pick_existing_enemy(self, owner_entity: int) -> int | None:
        candidates = [entity for entity, _ in self.world.get_component(RuleBasedAgent)]
        if not candidates:
            return None
        filtered = [entity for entity in candidates if entity != owner_entity]
        pool = filtered or candidates
        if not pool:
            return None
        return self._rng.choice(pool)

    def _spawn_enemy(self) -> int | None:
        if self._enemy_pool is None:
            return None
        try:
            enemy_entity = self._enemy_pool.spawn_random_enemy()  # type: ignore[attr-defined]
        except AttributeError:
            return None
        return enemy_entity

    def _default_owner_entity(self) -> int | None:
        players = [entity for entity, _ in self.world.get_component(HumanAgent)]
        if players:
            return players[0]
        owners = [entity for entity, _ in self.world.get_component(AbilityListOwner)]
        if owners:
            return owners[0]
        return None

    def _delete_entity(self, entity: int) -> None:
        try:
            self.world.delete_entity(entity, immediate=True)
        except Exception:
            try:
                self.world.delete_entity(entity)
            except Exception:
                pass
