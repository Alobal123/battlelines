from __future__ import annotations

import json
from pathlib import Path

from esper import World

from ecs.components.story_progress_tracker import StoryProgressTracker
from ecs.events.bus import (
    EVENT_ENEMY_DEFEATED,
    EVENT_GAME_MODE_CHANGED,
    EVENT_MENU_CONTINUE_SELECTED,
    EVENT_MENU_NEW_GAME_SELECTED,
    EventBus,
)


class StoryProgressSystem:
    """Tracks and persists long-term story progress across matches."""

    def __init__(
        self,
        world: World,
        event_bus: EventBus,
        *,
        save_path: Path | None = None,
        load_existing: bool = True,
    ) -> None:
        self.world = world
        self.event_bus = event_bus
        self._save_path = Path(save_path) if save_path is not None else self._default_save_path()
        self._tracker_entity = self._ensure_tracker_entity()
        self._has_progress = False

        self.event_bus.subscribe(EVENT_ENEMY_DEFEATED, self._on_enemy_defeated)
        self.event_bus.subscribe(EVENT_GAME_MODE_CHANGED, self._on_mode_changed)
        self.event_bus.subscribe(EVENT_MENU_NEW_GAME_SELECTED, self._on_new_game_selected)
        self.event_bus.subscribe(EVENT_MENU_CONTINUE_SELECTED, self._on_continue_selected)

        if load_existing:
            self.load_progress()
        else:
            self.save_progress()

    @staticmethod
    def _default_save_path() -> Path:
        return Path(__file__).resolve().parents[3] / "data" / "story_progress.json"

    def _ensure_tracker_entity(self) -> int:
        existing = list(self.world.get_component(StoryProgressTracker))
        if existing:
            return existing[0][0]
        return self.world.create_entity(StoryProgressTracker())

    def _tracker(self) -> StoryProgressTracker:
        return self.world.component_for_entity(self._tracker_entity, StoryProgressTracker)

    @property
    def has_progress(self) -> bool:
        return self._has_progress

    def load_progress(self) -> None:
        tracker = self._tracker()
        try:
            with self._save_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except FileNotFoundError:
            tracker.enemies_defeated = 0
            self._has_progress = False
            self.save_progress()
            return
        except json.JSONDecodeError:
            tracker.enemies_defeated = 0
            self._has_progress = False
            self.save_progress()
            return
        tracker.enemies_defeated = int(payload.get("enemies_defeated", 0))
        self._has_progress = tracker.enemies_defeated > 0

    def reset_progress(self) -> None:
        tracker = self._tracker()
        tracker.enemies_defeated = 0
        self._has_progress = False
        self.save_progress()

    def save_progress(self) -> None:
        tracker = self._tracker()
        self._save_path.parent.mkdir(parents=True, exist_ok=True)
        with self._save_path.open("w", encoding="utf-8") as handle:
            json.dump({"enemies_defeated": tracker.enemies_defeated}, handle, indent=2)
        self._has_progress = tracker.enemies_defeated > 0

    # Event handlers -----------------------------------------------------

    def _on_enemy_defeated(self, sender, **payload) -> None:
        tracker = self._tracker()
        tracker.enemies_defeated += 1
        self.save_progress()

    def _on_mode_changed(self, sender, **payload) -> None:
        self.save_progress()

    def _on_new_game_selected(self, sender, **payload) -> None:
        self.reset_progress()

    def _on_continue_selected(self, sender, **payload) -> None:
        self.load_progress()
