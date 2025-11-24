"""High-level coordinator for game mode transitions."""
from __future__ import annotations

import random
from typing import Any, cast

from esper import World

from ecs.components.choice_window import ChoiceWindow
from ecs.components.human_agent import HumanAgent
from ecs.components.location import CurrentLocation
from ecs.components.game_state import GameMode
from ecs.events.bus import (
    EVENT_ABILITY_CHOICE_GRANTED,
    EVENT_COMBAT_RESET,
    EVENT_COMBAT_START_REQUEST,
    EVENT_DIALOGUE_COMPLETED,
    EVENT_DIALOGUE_START,
    EVENT_LOCATION_CHOICE_GRANTED,
    EVENT_MATCH_READY,
    EVENT_MATCH_SETUP_REQUEST,
    EVENT_MENU_CONTINUE_SELECTED,
    EVENT_MENU_NEW_GAME_SELECTED,
    EVENT_SKILL_CHOICE_GRANTED,
    EventBus,
)
from ecs.factories.abilities import spawn_player_ability_choice
from ecs.factories.choice_window import clear_choice_window
from ecs.factories.locations import get_location_spec, spawn_location_choice_window
from ecs.factories.skills import spawn_player_skill_choice
from ecs.utils.game_state import set_game_mode


class GameFlowSystem:
    """Central coordinator for menu flow, drafts, and combat sequencing."""

    _MAX_ENEMIES_PER_LOCATION = 3

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
        self._pending_match: dict[str, object] | None = None
        self._remaining_enemy_slugs: list[str] = []
        self._current_location_slug: str | None = None
        self._current_press_id: int | None = None
        self._stage: str = "idle"

        # Expose reference so other systems (e.g., DefeatSystem) can adjust legacy behaviour.
        setattr(self.world, "_game_flow_system", self)

        self.event_bus.subscribe(EVENT_MENU_NEW_GAME_SELECTED, self._on_new_game)
        self.event_bus.subscribe(EVENT_MENU_CONTINUE_SELECTED, self._on_continue_game)
        self.event_bus.subscribe(EVENT_ABILITY_CHOICE_GRANTED, self._on_ability_choice_granted)
        self.event_bus.subscribe(EVENT_SKILL_CHOICE_GRANTED, self._on_skill_choice_granted)
        self.event_bus.subscribe(EVENT_LOCATION_CHOICE_GRANTED, self._on_location_choice_granted)
        self.event_bus.subscribe(EVENT_COMBAT_RESET, self._on_combat_reset)
        self.event_bus.subscribe(EVENT_MATCH_READY, self._on_match_ready)
        self.event_bus.subscribe(EVENT_DIALOGUE_COMPLETED, self._on_dialogue_completed)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_new_game(self, sender, **payload) -> None:
        self._reset_flow_state()
        self._current_press_id = payload.get("press_id")
        self._begin_ability_cycle(require_empty_owner=True, reason="new_game")

    def _on_continue_game(self, sender, **payload) -> None:
        self._current_press_id = payload.get("press_id")
        self._request_match_setup(reason="continue_game", press_id=self._current_press_id)

    def _on_ability_choice_granted(self, sender, **payload) -> None:
        owner_entity = payload.get("owner_entity")
        primary = self._primary_player()
        if primary is None or owner_entity != primary:
            return
        self._close_choice_window(payload.get("window_entity"))
        self._current_press_id = payload.get("press_id", self._current_press_id)
        self._stage = "ability_granted"
        self._begin_skill_cycle()

    def _on_skill_choice_granted(self, sender, **payload) -> None:
        owner_entity = payload.get("owner_entity")
        primary = self._primary_player()
        if primary is None or owner_entity != primary:
            return
        self._close_choice_window(payload.get("window_entity"))
        self._current_press_id = payload.get("press_id", self._current_press_id)
        self._stage = "skill_granted"
        self._begin_location_cycle()

    def _on_location_choice_granted(self, sender, **payload) -> None:
        owner_entity = payload.get("owner_entity")
        primary = self._primary_player()
        if primary is None or owner_entity != primary:
            return
        self._close_choice_window(payload.get("window_entity"))
        self._current_press_id = payload.get("press_id", self._current_press_id)
        location_slug = payload.get("location_slug")
        if location_slug is None:
            self._cycle_complete()
            return
        self._prepare_location_plan(primary, location_slug)
        self._start_next_battle()

    def _on_combat_reset(self, sender, **payload) -> None:
        reason = payload.get("reason")
        if reason != "enemy_defeated":
            return
        self._current_press_id = payload.get("press_id", self._current_press_id)
        if self._remaining_enemy_slugs:
            self._start_next_battle()
        else:
            self._cycle_complete()

    def _on_match_ready(self, sender, **payload) -> None:
        owner_entity = payload.get("owner_entity")
        if owner_entity is None:
            return
        enemy_entity = payload.get("enemy_entity")
        dialogue_mode = payload.get("dialogue_mode")
        if not isinstance(dialogue_mode, GameMode):
            dialogue_mode = GameMode.DIALOGUE
        resume_mode = payload.get("resume_mode")
        if not isinstance(resume_mode, GameMode):
            resume_mode = GameMode.COMBAT
        fallback_mode = payload.get("fallback_mode")
        if not isinstance(fallback_mode, GameMode):
            fallback_mode = GameMode.COMBAT
        press_id = payload.get("press_id", self._current_press_id)
        if enemy_entity is None:
            set_game_mode(
                self.world,
                self.event_bus,
                fallback_mode,
                input_guard_press_id=press_id,
            )
            self._pending_match = None
            return
        self._pending_match = {
            "player": owner_entity,
            "enemy": enemy_entity,
            "resume_mode": resume_mode,
        }
        set_game_mode(
            self.world,
            self.event_bus,
            dialogue_mode,
            input_guard_press_id=press_id,
        )
        dialogue_kwargs = {
            "left_entity": owner_entity,
            "right_entity": enemy_entity,
            "resume_mode": resume_mode,
            "originating_press_id": press_id,
        }
        if "reason" in payload:
            dialogue_kwargs["reason"] = payload["reason"]
        if "location_slug" in payload:
            dialogue_kwargs["location_slug"] = payload["location_slug"]
        self.event_bus.emit(EVENT_DIALOGUE_START, **dialogue_kwargs)

    def _on_dialogue_completed(self, sender, **payload) -> None:
        pending = self._pending_match
        if not pending:
            return
        player_entity = payload.get("left_entity")
        enemy_entity = payload.get("right_entity")
        if player_entity != pending.get("player") or enemy_entity != pending.get("enemy"):
            self._pending_match = None
            return
        resume_mode_payload = payload.get("resume_mode")
        if isinstance(resume_mode_payload, GameMode):
            resume_mode = resume_mode_payload
        else:
            resume_mode = cast(GameMode, pending.get("resume_mode", GameMode.COMBAT))
        set_game_mode(self.world, self.event_bus, resume_mode)
        self.event_bus.emit(
            EVENT_COMBAT_START_REQUEST,
            player_entity=player_entity,
            enemy_entity=enemy_entity,
            resume_mode=resume_mode,
        )
        self._pending_match = None

    # ------------------------------------------------------------------
    # Draft helpers
    # ------------------------------------------------------------------

    def _begin_ability_cycle(self, *, require_empty_owner: bool, reason: str) -> None:
        success = self._open_ability_draft(require_empty_owner=require_empty_owner, reason=reason)
        if not success:
            self._stage = "ability_skipped"
            self._begin_skill_cycle()

    def _begin_skill_cycle(self) -> None:
        success = self._open_skill_draft()
        if not success:
            self._stage = "skill_skipped"
            self._begin_location_cycle()

    def _begin_location_cycle(self) -> None:
        success = self._open_location_choice()
        if not success:
            self._cycle_complete()

    def _open_ability_draft(self, *, require_empty_owner: bool, reason: str) -> bool:
        owner_entity = self._primary_player()
        if owner_entity is None:
            return False
        window_entity = spawn_player_ability_choice(
            self.world,
            event_bus=self.event_bus,
            owner_entity=owner_entity,
            rng=self._rng,
            title="Choose an Ability" if reason != "new_game" else "Choose Your First Ability",
            require_empty_owner=require_empty_owner,
            press_id=self._current_press_id,
        )
        if window_entity is None:
            return False
        self._stage = "ability_draft"
        return True

    def _open_skill_draft(self) -> bool:
        owner_entity = self._primary_player()
        if owner_entity is None:
            return False
        window_entity = spawn_player_skill_choice(
            self.world,
            event_bus=self.event_bus,
            owner_entity=owner_entity,
            rng=self._rng,
            title="Choose a Skill",
            press_id=self._current_press_id,
        )
        if window_entity is None:
            return False
        self._stage = "skill_draft"
        return True

    def _open_location_choice(self) -> bool:
        owner_entity = self._primary_player()
        if owner_entity is None:
            return False
        window_entity = spawn_location_choice_window(
            self.world,
            owner_entity=owner_entity,
            event_bus=self.event_bus,
            rng=self._rng,
            press_id=self._current_press_id,
        )
        if window_entity is None:
            return False
        self._stage = "location_draft"
        return True

    # ------------------------------------------------------------------
    # Location and combat helpers
    # ------------------------------------------------------------------

    def _prepare_location_plan(self, owner_entity: int, location_slug: str) -> None:
        self._current_location_slug = location_slug
        self._remaining_enemy_slugs = []
        enemy_slugs: list[str] = []
        try:
            current = self.world.component_for_entity(owner_entity, CurrentLocation)
        except KeyError:
            current = None
        if current is not None and current.enemy_names:
            enemy_slugs.extend(name for name in current.enemy_names if name)
        if not enemy_slugs:
            spec = get_location_spec(location_slug)
            if spec is not None:
                enemy_slugs.extend(name for name in spec.enemy_names if name)
        if not enemy_slugs:
            # Fallback: allow enemy pool or match setup to decide later.
            self._remaining_enemy_slugs = []
            return
        deduped = list(dict.fromkeys(enemy_slugs))
        self._rng.shuffle(deduped)
        self._remaining_enemy_slugs = deduped[: self._MAX_ENEMIES_PER_LOCATION]

    def _start_next_battle(self) -> None:
        owner_entity = self._primary_player()
        if owner_entity is None:
            return
        enemy_slug = None
        if self._remaining_enemy_slugs:
            enemy_slug = self._remaining_enemy_slugs.pop(0)
        enemy_entity = None
        if enemy_slug is not None:
            enemy_entity = self._spawn_enemy_by_name(enemy_slug)
        if enemy_entity is None:
            enemy_entity = self._spawn_random_enemy()
        if enemy_entity is None:
            self._cycle_complete()
            return
        reason = "location_battle"
        if self._current_location_slug:
            reason = f"location:{self._current_location_slug}:{enemy_slug or 'unknown'}"
        self._request_match_setup(
            next_enemy=enemy_entity,
            reason=reason,
            press_id=self._current_press_id,
            location_slug=self._current_location_slug,
        )

    def _cycle_complete(self) -> None:
        self._current_location_slug = None
        self._remaining_enemy_slugs = []
        self._stage = "idle"
        self._begin_ability_cycle(require_empty_owner=False, reason="loop_continue")

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def _request_match_setup(
        self,
        *,
        next_enemy: int | None = None,
        reason: str,
        press_id: int | None,
        location_slug: str | None = None,
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
            location_slug=location_slug,
        )

    def _primary_player(self) -> int | None:
        players = [entity for entity, _ in self.world.get_component(HumanAgent)]
        if players:
            return players[0]
        return None

    def _reset_flow_state(self) -> None:
        self._pending_match = None
        self._remaining_enemy_slugs = []
        self._current_location_slug = None
        self._stage = "idle"

    def _spawn_enemy_by_name(self, slug: str) -> int | None:
        enemy_pool = getattr(self.world, "enemy_pool", None)
        if enemy_pool is None:
            return None
        try:
            return enemy_pool.create_enemy(slug)  # type: ignore[attr-defined]
        except ValueError:
            return None

    def _spawn_random_enemy(self) -> int | None:
        enemy_pool = getattr(self.world, "enemy_pool", None)
        if enemy_pool is None:
            return None
        try:
            return enemy_pool.spawn_random_enemy()  # type: ignore[attr-defined]
        except AttributeError:
            return None

    def _close_choice_window(self, window_entity: int | None) -> None:
        if window_entity is None:
            clear_choice_window(self.world)
            return
        try:
            window = self.world.component_for_entity(window_entity, ChoiceWindow)
        except KeyError:
            clear_choice_window(self.world)
            return
        for option_entity in list(window.option_entities):
            self._delete_entity(option_entity)
        self._delete_entity(window_entity)

    def _delete_entity(self, entity: int) -> None:
        try:
            self.world.delete_entity(entity, immediate=True)
        except Exception:
            try:
                self.world.delete_entity(entity)
            except Exception:
                pass
