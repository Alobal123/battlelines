from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

from esper import World

from ecs.components.character import Character
from ecs.components.dialogue_session import DialogueLine, DialogueSession
from ecs.components.game_state import GameMode, GameState
from ecs.events.bus import (
    EVENT_DIALOGUE_ADVANCE,
    EVENT_DIALOGUE_COMPLETED,
    EVENT_DIALOGUE_START,
    EVENT_MOUSE_PRESS,
    EventBus,
)
from ecs.utils.game_state import set_game_mode


@dataclass(slots=True)
class _ParticipantInfo:
    entity: int
    name: str
    portrait: str | None


class DialogueSystem:
    """Manages narrative dialogue sequences between combats."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_DIALOGUE_START, self._on_start_dialogue)
        self.event_bus.subscribe(EVENT_DIALOGUE_ADVANCE, self._on_advance_requested)
        self.event_bus.subscribe(EVENT_MOUSE_PRESS, self._on_mouse_press)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_start_dialogue(self, sender, **payload) -> None:
        left_entity = payload.get("left_entity") or payload.get("player_entity")
        right_entity = payload.get("right_entity") or payload.get("enemy_entity")
        if left_entity is None or right_entity is None:
            return
        resume_mode = payload.get("resume_mode", GameMode.COMBAT)
        lines_payload = payload.get("lines")
        lines = self._build_lines(left_entity, right_entity, lines_payload)
        if not lines:
            return
        self._create_or_update_session(left_entity, right_entity, lines, resume_mode)
        set_game_mode(self.world, self.event_bus, GameMode.DIALOGUE)

    def _on_mouse_press(self, sender, **payload) -> None:
        button = payload.get("button")
        if button not in (1, "left", None):
            return
        if not self._is_dialogue_active():
            return
        self._advance_dialogue()

    def _on_advance_requested(self, sender, **payload) -> None:
        if not self._is_dialogue_active():
            return
        self._advance_dialogue()

    # ------------------------------------------------------------------
    # Public input helpers (for key presses)
    # ------------------------------------------------------------------
    def handle_key_press(self, symbol: int, modifiers: int) -> None:
        if not self._is_dialogue_active():
            return
        # Enter (13) and Space (32) advance the conversation.
        if symbol in (13, 32, 65293):
            self._advance_dialogue()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _is_dialogue_active(self) -> bool:
        state = self._get_game_state()
        return state is not None and state.mode == GameMode.DIALOGUE and self._current_session_entity() is not None

    def _get_game_state(self) -> GameState | None:
        entries = list(self.world.get_component(GameState))
        if not entries:
            return None
        return entries[0][1]

    def _current_session_entity(self) -> int | None:
        sessions = list(self.world.get_component(DialogueSession))
        if not sessions:
            return None
        return sessions[0][0]

    def _current_session(self) -> DialogueSession | None:
        sessions = list(self.world.get_component(DialogueSession))
        if not sessions:
            return None
        return sessions[0][1]

    def _create_or_update_session(
        self,
        left_entity: int,
        right_entity: int,
        lines: Sequence[DialogueLine],
        resume_mode: GameMode,
    ) -> None:
        session_entries = list(self.world.get_component(DialogueSession))
        if session_entries:
            entity, session = session_entries[0]
            session.left_entity = left_entity
            session.right_entity = right_entity
            session.lines = tuple(lines)
            session.current_index = 0
            session.resume_mode = resume_mode
        else:
            entity = self.world.create_entity(
                DialogueSession(
                    left_entity=left_entity,
                    right_entity=right_entity,
                    lines=tuple(lines),
                    current_index=0,
                    resume_mode=resume_mode,
                )
            )
        # Ensure entity keeps the component updated (already stored via reference).
        return None

    def _advance_dialogue(self) -> None:
        session_entity = self._current_session_entity()
        if session_entity is None:
            return
        session = self.world.component_for_entity(session_entity, DialogueSession)
        if session.advance():
            return
        # Dialogue completed; transition back to the desired mode.
        resume_mode = session.resume_mode
        left_entity = session.left_entity
        right_entity = session.right_entity
        self.world.delete_entity(session_entity)
        set_game_mode(self.world, self.event_bus, resume_mode)
        self.event_bus.emit(
            EVENT_DIALOGUE_COMPLETED,
            left_entity=left_entity,
            right_entity=right_entity,
            resume_mode=resume_mode,
        )

    def _build_lines(
        self,
        left_entity: int,
        right_entity: int,
        payload: Iterable | None,
    ) -> Sequence[DialogueLine]:
        if payload:
            return tuple(self._normalize_lines(payload))
        return self._default_lines(left_entity, right_entity)

    def _normalize_lines(self, payload: Iterable) -> List[DialogueLine]:
        lines: List[DialogueLine] = []
        for item in payload:
            if isinstance(item, DialogueLine):
                lines.append(item)
                continue
            if isinstance(item, dict):
                speaker = item.get("speaker") or item.get("speaker_entity")
                text = item.get("text", "")
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                speaker, text = item[0], item[1]
            else:
                continue
            if speaker is None:
                continue
            lines.append(DialogueLine(speaker_entity=int(speaker), text=str(text)))
        return lines

    def _default_lines(self, left_entity: int, right_entity: int) -> Sequence[DialogueLine]:
        left_info = self._participant_info(left_entity)
        right_info = self._participant_info(right_entity)
        if left_info is None or right_info is None:
            return ()
        return (
            DialogueLine(
                speaker_entity=left_info.entity,
                text=f"{right_info.name}, your reign of terror ends here!",
            ),
            DialogueLine(
                speaker_entity=right_info.entity,
                text="Bold words. Let's see if you can back them up.",
            ),
            DialogueLine(
                speaker_entity=left_info.entity,
                text="Save the bravado. Fiora always keeps her promises.",
            ),
        )

    def _participant_info(self, entity: int) -> _ParticipantInfo | None:
        try:
            character = self.world.component_for_entity(entity, Character)
        except KeyError:
            return None
        return _ParticipantInfo(
            entity=entity,
            name=character.name or "???",
            portrait=character.portrait_path,
        )
