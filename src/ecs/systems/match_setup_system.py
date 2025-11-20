"""Systems handling opponent selection and match flow transitions."""
from __future__ import annotations

import random
from typing import Any, Callable, Dict

from esper import World

from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.choice_window import ChoiceWindow
from ecs.components.game_state import GameMode
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.events.bus import (
    EVENT_ABILITY_CHOICE_GRANTED,
    EVENT_SKILL_POOL_REQUEST,
    EVENT_SKILL_POOL_OFFER,
    EVENT_SKILL_CHOICE_GRANTED,
    EVENT_DIALOGUE_START,
    EVENT_MATCH_SETUP_REQUEST,
    EventBus,
)
from ecs.factories.choice_window import clear_choice_window
from ecs.factories.skills import spawn_skill_choice_window
from ecs.utils.game_state import set_game_mode


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
        clear_window: bool = True,
        on_setup_complete: FlowCallback | None = None,
    ) -> None:
        self.world = world
        self.event_bus = event_bus
        self._rng = rng or getattr(world, "random", None) or random.SystemRandom()
        self._enemy_pool = enemy_pool or getattr(world, "enemy_pool", None)
        self._dialogue_mode = dialogue_mode
        self._resume_mode = resume_mode
        self._fallback_mode = fallback_mode
        self._clear_window = clear_window
        self._on_setup_complete = on_setup_complete
        self._skill_request_counter = 0
        self._pending_skill_request_id: int | None = None
        self._pending_skill_context: Dict[str, Any] | None = None
        self.event_bus.subscribe(EVENT_ABILITY_CHOICE_GRANTED, self._on_ability_choice_granted)
        self.event_bus.subscribe(EVENT_SKILL_POOL_OFFER, self._on_skill_pool_offer)
        self.event_bus.subscribe(EVENT_SKILL_CHOICE_GRANTED, self._on_skill_choice_granted)
        self.event_bus.subscribe(EVENT_MATCH_SETUP_REQUEST, self._on_match_setup_request)

    def _on_ability_choice_granted(self, sender, **payload) -> None:
        owner_entity = payload.get("owner_entity")
        if owner_entity is None:
            return
        if not self._owner_has_abilities(owner_entity):
            return
        window_entity = payload.get("window_entity")
        press_id = payload.get("press_id")
        if self._clear_window:
            self._close_choice_window(window_entity)
        if self._request_skill_choice(owner_entity, press_id):
            return
        self._complete_setup(owner_entity, press_id)

    def _request_skill_choice(self, owner_entity: int, press_id: int | None) -> bool:
        if self._pending_skill_request_id is not None:
            self._pending_skill_context = None
            self._pending_skill_request_id = None
        self._skill_request_counter += 1
        request_id = self._skill_request_counter
        context: Dict[str, Any] = {
            "owner_entity": owner_entity,
            "press_id": press_id,
            "window_entity": None,
        }
        self._pending_skill_request_id = request_id
        self._pending_skill_context = context
        self.event_bus.emit(
            EVENT_SKILL_POOL_REQUEST,
            owner_entity=owner_entity,
            count=3,
            request_id=request_id,
        )
        current_context = self._pending_skill_context
        if current_context is None:
            self._pending_skill_request_id = None
            return False
        if current_context.get("window_entity") is None:
            self._pending_skill_context = None
            self._pending_skill_request_id = None
            return False
        return True

    def _on_skill_pool_offer(self, sender, **payload) -> None:
        request_id = payload.get("request_id")
        if request_id != self._pending_skill_request_id:
            return
        context = self._pending_skill_context
        if context is None:
            self._pending_skill_request_id = None
            return
        owner_entity = payload.get("owner_entity")
        if owner_entity is None or owner_entity != context.get("owner_entity"):
            self._pending_skill_context = None
            self._pending_skill_request_id = None
            return
        skills = list(payload.get("skills") or [])
        if not skills:
            self._pending_skill_context = None
            self._pending_skill_request_id = None
            return
        window_entity = spawn_skill_choice_window(
            self.world,
            owner_entity=owner_entity,
            skill_names=skills,
            event_bus=self.event_bus,
            rng=self._rng,
            title="Choose a Skill",
            press_id=context.get("press_id"),
        )
        if window_entity is None:
            self._pending_skill_context = None
            self._pending_skill_request_id = None
            return
        context["window_entity"] = window_entity

    def _on_skill_choice_granted(self, sender, **payload) -> None:
        owner_entity = payload.get("owner_entity")
        if owner_entity is None:
            return
        context = self._pending_skill_context
        if context is None or context.get("owner_entity") != owner_entity:
            if self._clear_window:
                self._close_choice_window(payload.get("window_entity"))
            return
        if self._clear_window:
            self._close_choice_window(payload.get("window_entity"))
        press_id = payload.get("press_id")
        if press_id is None:
            press_id = context.get("press_id")
        self._pending_skill_context = None
        self._pending_skill_request_id = None
        self._complete_setup(owner_entity, press_id)

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
        if enemy_entity is None:
            set_game_mode(
                self.world,
                self.event_bus,
                self._fallback_mode,
                input_guard_press_id=payload.get("press_id"),
            )
            return
        self._start_dialogue(owner_entity, enemy_entity, press_id=payload.get("press_id"))
        if self._on_setup_complete is not None:
            self._on_setup_complete()

    def _complete_setup(self, owner_entity: int, press_id: int | None) -> None:
        enemy_entity = self._pick_existing_enemy(owner_entity)
        if enemy_entity is None:
            enemy_entity = self._spawn_enemy()
        if enemy_entity is not None:
            self._start_dialogue(owner_entity, enemy_entity, press_id=press_id)
        else:
            set_game_mode(
                self.world,
                self.event_bus,
                self._fallback_mode,
                input_guard_press_id=press_id,
            )
        if self._on_setup_complete is not None:
            self._on_setup_complete()

    def _owner_has_abilities(self, owner_entity: int) -> bool:
        try:
            self.world.component_for_entity(owner_entity, AbilityListOwner)
            return True
        except KeyError:
            return False

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

    def _start_dialogue(self, owner_entity: int, enemy_entity: int, *, press_id: int | None = None) -> None:
        set_game_mode(
            self.world,
            self.event_bus,
            self._dialogue_mode,
            input_guard_press_id=press_id,
        )
        self.event_bus.emit(
            EVENT_DIALOGUE_START,
            left_entity=owner_entity,
            right_entity=enemy_entity,
            resume_mode=self._resume_mode,
            originating_press_id=press_id,
        )

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
