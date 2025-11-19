"""High-level coordinator for game mode transitions."""
from __future__ import annotations

import random

from esper import World

from ecs.components.human_agent import HumanAgent
from ecs.events.bus import (
    EVENT_COMBAT_RESET,
    EVENT_MATCH_SETUP_REQUEST,
    EVENT_MENU_CONTINUE_SELECTED,
    EVENT_MENU_NEW_GAME_SELECTED,
    EventBus,
)
from ecs.factories.abilities import spawn_player_ability_choice


class GameFlowSystem:
    """Decides which major mode to enter when narrative beats complete."""

    def __init__(
        self,
        world: World,
        event_bus: EventBus,
        *,
        rng: random.Random | None = None,
    ) -> None:
        self.world = world
        self.event_bus = event_bus
        self._rng = rng or getattr(world, "random", None) or random.SystemRandom()
        self.event_bus.subscribe(EVENT_MENU_NEW_GAME_SELECTED, self._on_new_game)
        self.event_bus.subscribe(EVENT_MENU_CONTINUE_SELECTED, self._on_continue_game)
        self.event_bus.subscribe(EVENT_COMBAT_RESET, self._on_combat_reset)

    def _on_new_game(self, sender, **payload) -> None:
        drafted = self._enter_ability_draft(
            reason="new_game",
            require_empty_owner=True,
            title="Choose Your First Ability",
            press_id=payload.get("press_id"),
        )
        if not drafted:
            self._request_match_setup(reason="new_game:no_draft_available", press_id=payload.get("press_id"))

    def _on_continue_game(self, sender, **payload) -> None:
        drafted = self._enter_ability_draft(
            reason="continue_game",
            require_empty_owner=True,
            title="Choose Your First Ability",
            press_id=payload.get("press_id"),
        )
        if not drafted:
            self._request_match_setup(reason="continue_game:no_draft_available", press_id=payload.get("press_id"))

    def _on_combat_reset(self, sender, **payload) -> None:
        reason = payload.get("reason")
        if reason != "enemy_defeated":
            return
        next_enemy = payload.get("next_enemy")
        drafted = self._enter_ability_draft(
            reason="combat_victory",
            require_empty_owner=False,
            title="Choose a New Ability",
        )
        if not drafted:
            self._request_match_setup(next_enemy=next_enemy, reason="combat_reset:no_draft_available")

    def _enter_ability_draft(
        self,
        *,
        reason: str,
        require_empty_owner: bool,
        title: str,
        press_id: int | None = None,
    ) -> bool:
        owner_entity = self._primary_player()
        if owner_entity is None:
            return False
        window_entity = spawn_player_ability_choice(
            self.world,
            event_bus=self.event_bus,
            owner_entity=owner_entity,
            rng=self._rng,
            title=title,
            require_empty_owner=require_empty_owner,
            press_id=press_id,
        )
        return window_entity is not None

    def _request_match_setup(
        self,
        *,
        next_enemy: int | None = None,
        reason: str,
        press_id: int | None = None,
    ) -> None:
        owner_entity = self._primary_player()
        if owner_entity is None:
            return
        self.event_bus.emit(
            EVENT_MATCH_SETUP_REQUEST,
            owner_entity=owner_entity,
            enemy_entity=next_enemy,
            reason=reason,
            press_id=press_id,
        )

    def _primary_player(self) -> int | None:
        players = [entity for entity, _ in self.world.get_component(HumanAgent)]
        if players:
            return players[0]
        return None
