from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ecs.components.game_state import GameMode


@dataclass(slots=True)
class DialogueLine:
    """Single line of dialogue spoken by one of the participants."""

    speaker_entity: int
    text: str


@dataclass(slots=True)
class DialogueSession:
    """Tracks the current story dialogue between two characters."""

    left_entity: int
    right_entity: int
    lines: tuple[DialogueLine, ...]
    current_index: int = 0
    resume_mode: GameMode = GameMode.COMBAT

    def advance(self) -> bool:
        """Advance to the next line.

        Returns True when the dialogue still has lines remaining, False when
        the sequence is finished.
        """

        if self.current_index < len(self.lines) - 1:
            self.current_index += 1
            return True
        return False

    @property
    def current_line(self) -> DialogueLine | None:
        if not self.lines:
            return None
        if self.current_index < 0 or self.current_index >= len(self.lines):
            return None
        return self.lines[self.current_index]

    @property
    def participants(self) -> Sequence[int]:
        return (self.left_entity, self.right_entity)
