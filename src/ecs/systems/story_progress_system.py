from __future__ import annotations

import json
from pathlib import Path

from esper import World

from ecs.components.story_progress_tracker import StoryProgressTracker
from ecs.components.forbidden_knowledge import ForbiddenKnowledge
from ecs.components.human_agent import HumanAgent
from ecs.components.health import Health
from ecs.events.bus import (
    EVENT_ENEMY_DEFEATED,
    EVENT_GAME_MODE_CHANGED,
    EVENT_MENU_CONTINUE_SELECTED,
    EVENT_MENU_NEW_GAME_SELECTED,
    EVENT_DIALOGUE_COMPLETED,
    EVENT_LOCATION_ENTERED,
    EVENT_LOCATION_COMPLETED,
    EVENT_ABILITY_UNLOCKED,
    EVENT_SKILL_GAINED,
    EVENT_FORBIDDEN_KNOWLEDGE_CHANGED,
    EventBus,
)
from ecs.systems.board_ops import get_tile_registry


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
        self.event_bus.subscribe(EVENT_DIALOGUE_COMPLETED, self._on_dialogue_completed)
        self.event_bus.subscribe(EVENT_LOCATION_ENTERED, self._on_location_entered)
        self.event_bus.subscribe(EVENT_LOCATION_COMPLETED, self._on_location_completed)
        self.event_bus.subscribe(EVENT_ABILITY_UNLOCKED, self._on_ability_unlocked)
        self.event_bus.subscribe(EVENT_SKILL_GAINED, self._on_skill_gained)

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
            tracker.locations_visited = set()
            tracker.enemies_encountered = set()
            tracker.dialogues_completed = set()
            tracker.abilities_unlocked = []
            tracker.skills_gained = set()
            tracker.locations_completed = 0
            self._has_progress = False
            self.save_progress()
            return
        except json.JSONDecodeError:
            tracker.enemies_defeated = 0
            tracker.locations_visited = set()
            tracker.enemies_encountered = set()
            tracker.dialogues_completed = set()
            tracker.abilities_unlocked = []
            tracker.skills_gained = set()
            tracker.locations_completed = 0
            self._has_progress = False
            self.save_progress()
            return
        tracker.enemies_defeated = int(payload.get("enemies_defeated", 0))
        tracker.locations_visited = set(payload.get("locations_visited", []))
        tracker.enemies_encountered = set(payload.get("enemies_encountered", []))
        tracker.dialogues_completed = set(payload.get("dialogues_completed", []))
        tracker.abilities_unlocked = list(payload.get("abilities_unlocked", []))
        tracker.skills_gained = set(payload.get("skills_gained", []))
        tracker.locations_completed = int(payload.get("locations_completed", 0))
        self._has_progress = tracker.enemies_defeated > 0

    def reset_progress(self) -> None:
        tracker = self._tracker()
        tracker.enemies_defeated = 0
        tracker.locations_visited = set()
        tracker.enemies_encountered = set()
        tracker.dialogues_completed = set()
        tracker.abilities_unlocked = []
        tracker.skills_gained = set()
        tracker.locations_completed = 0
        self._has_progress = False
        self._reset_forbidden_knowledge_meter()
        self.save_progress()

    def save_progress(self) -> None:
        tracker = self._tracker()
        self._save_path.parent.mkdir(parents=True, exist_ok=True)
        with self._save_path.open("w", encoding="utf-8") as handle:
            json.dump({
                "enemies_defeated": tracker.enemies_defeated,
                "locations_visited": list(tracker.locations_visited),
                "enemies_encountered": list(tracker.enemies_encountered),
                "dialogues_completed": list(tracker.dialogues_completed),
                "abilities_unlocked": tracker.abilities_unlocked,
                "skills_gained": list(tracker.skills_gained),
                "locations_completed": tracker.locations_completed,
            }, handle, indent=2)
        self._has_progress = tracker.enemies_defeated > 0

    # Event handlers -----------------------------------------------------

    def _on_enemy_defeated(self, sender, **payload) -> None:
        tracker = self._tracker()
        tracker.enemies_defeated += 1
        
        # Increment current location progress
        tracker.current_location_enemies_defeated += 1
        
        # Track enemy slug (factory name) if provided for EnemyPoolSystem filtering
        entity = payload.get("entity")
        if entity is not None:
            try:
                from ecs.components.character import Character
                char = self.world.component_for_entity(entity, Character)
                # Store the slug (factory identifier) for pool filtering
                tracker.enemies_encountered.add(char.slug)
            except (KeyError, ImportError):
                pass
        
        # Check if location is completed (3 enemies defeated)
        if tracker.current_location_enemies_defeated >= 3:
            self.event_bus.emit(
                EVENT_LOCATION_COMPLETED,
                location_slug=tracker.current_location_slug,
                enemies_defeated=tracker.current_location_enemies_defeated
            )
            self._reset_location_resources()
        
        self.save_progress()

    def _on_mode_changed(self, sender, **payload) -> None:
        self.save_progress()

    def _on_new_game_selected(self, sender, **payload) -> None:
        self.reset_progress()

    def _on_continue_selected(self, sender, **payload) -> None:
        self.load_progress()

    def _on_dialogue_completed(self, sender, **payload) -> None:
        tracker = self._tracker()
        # Track dialogue by participant entities or a unique dialogue ID
        left_entity = payload.get("left_entity")
        right_entity = payload.get("right_entity")
        if left_entity is not None and right_entity is not None:
            dialogue_id = f"dialogue_{left_entity}_{right_entity}"
            tracker.dialogues_completed.add(dialogue_id)
        self.save_progress()

    def _on_location_entered(self, sender, **payload) -> None:
        tracker = self._tracker()
        location_name = payload.get("location_name")
        if location_name:
            tracker.locations_visited.add(location_name)
            # Reset current location progress counter
            tracker.current_location_slug = location_name
            tracker.current_location_enemies_defeated = 0
        self.save_progress()

    def _on_location_completed(self, sender, **payload) -> None:
        tracker = self._tracker()
        tracker.locations_completed += 1
        tracker.current_location_enemies_defeated = 0
        self.save_progress()

    def _on_ability_unlocked(self, sender, **payload) -> None:
        tracker = self._tracker()
        ability_name = payload.get("ability_name")
        if ability_name and ability_name not in tracker.abilities_unlocked:
            tracker.abilities_unlocked.append(ability_name)
        self.save_progress()

    def _on_skill_gained(self, sender, **payload) -> None:
        tracker = self._tracker()
        skill_name = payload.get("skill_name")
        if skill_name:
            tracker.skills_gained.add(skill_name)
        self.save_progress()

    def _reset_location_resources(self) -> None:
        tracker = self._tracker()
        tracker.current_location_enemies_defeated = 0
        self._restore_player_health()
        self._reset_forbidden_knowledge_meter()

    def _restore_player_health(self) -> None:
        for entity, _ in list(self.world.get_component(HumanAgent)):
            try:
                health = self.world.component_for_entity(entity, Health)
            except (KeyError, ValueError):
                continue
            health.current = health.max_hp

    def _reset_forbidden_knowledge_meter(self) -> None:
        entries = list(self.world.get_component(ForbiddenKnowledge))
        if not entries:
            return
        entity, meter = entries[0]
        previous_value = meter.value
        was_released = meter.chaos_released
        meter.value = 0
        meter.chaos_released = False
        if meter.baseline_spawnable:
            try:
                registry = get_tile_registry(self.world)
            except RuntimeError:
                registry = None
            else:
                registry.set_spawnable(meter.baseline_spawnable)
        delta = meter.value - previous_value
        if delta != 0 or was_released:
            self.event_bus.emit(
                EVENT_FORBIDDEN_KNOWLEDGE_CHANGED,
                entity=entity,
                value=meter.value,
                max_value=meter.max_value,
                delta=delta,
            )
