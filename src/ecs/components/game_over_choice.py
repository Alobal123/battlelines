from dataclasses import dataclass


@dataclass(slots=True)
class GameOverChoice:
    """Marks a choice option that should resolve game-over flow."""

    action: str = "return_to_menu"
