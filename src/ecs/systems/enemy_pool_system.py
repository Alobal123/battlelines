from __future__ import annotations

import importlib
import pkgutil
import random
from typing import Callable, Dict, Iterable, Sequence, cast

from esper import World

from ecs.components.story_progress_tracker import StoryProgressTracker
from ecs.components.health import Health
from ecs.events.bus import (
    EventBus,
    EVENT_ENEMY_POOL_OFFER,
    EVENT_ENEMY_POOL_REQUEST,
)


def _discover_enemy_factories() -> Dict[str, Callable[[World], int]]:
    builders: Dict[str, Callable[[World], int]] = {}
    package_name = "ecs.factories.enemies"
    package = importlib.import_module(package_name)
    for module in _iter_modules(package_name, package):
        for attr_name in dir(module):
            if not attr_name.startswith("create_enemy_"):
                continue
            factory = getattr(module, attr_name)
            if callable(factory):
                enemy_name = attr_name[len("create_enemy_") :]
                builders.setdefault(enemy_name, cast(Callable[[World], int], factory))
    return builders


def _iter_modules(package_name: str, package) -> Iterable:
    yield package
    package_path = getattr(package, "__path__", None)
    if not package_path:
        return
    for module_info in pkgutil.iter_modules(package_path):
        if module_info.name.startswith("__"):
            continue
        yield importlib.import_module(f"{package_name}.{module_info.name}")


class EnemyPoolSystem:
    """Provides enemy selection capabilities for combat setup."""

    def __init__(self, world: World, event_bus: EventBus, *, rng: random.Random | None = None) -> None:
        self.world = world
        self.event_bus = event_bus
        candidate_rng = rng or getattr(world, "random", None)
        self._rng: random.Random = candidate_rng or random.SystemRandom()
        self._factories: Dict[str, Callable[[World], int]] = _discover_enemy_factories()
        self._names: Sequence[str] = tuple(sorted(self._factories.keys()))
        self._last_enemy_name: str | None = None
        self.event_bus.subscribe(EVENT_ENEMY_POOL_REQUEST, self._on_request)

    def known_enemy_names(self) -> Sequence[str]:
        return self._names

    def _get_available_enemies(self) -> Sequence[str]:
        """Return enemy names that haven't been encountered yet in this game."""
        tracker_entries = list(self.world.get_component(StoryProgressTracker))
        if not tracker_entries:
            return self._names
        _, tracker = tracker_entries[0]
        return tuple(name for name in self._names if name not in tracker.enemies_encountered)

    def create_enemy(self, name: str) -> int:
        factory = self._factories.get(name)
        if factory is None:
            raise ValueError(f"Unknown enemy '{name}'")
        enemy = factory(self.world)
        self._last_enemy_name = name
        self._apply_enemy_scaling(enemy)
        return enemy

    def random_enemy_name(self) -> str | None:
        available = self._get_available_enemies()
        if not available:
            return None
        if len(available) == 1:
            choice = available[0]
        else:
            choice = self._rng.choice(available)
            if choice == self._last_enemy_name:
                # Try to avoid repeating the same enemy consecutively when alternatives exist.
                for _ in range(len(available) - 1):
                    new_choice = self._rng.choice(available)
                    if new_choice != self._last_enemy_name:
                        choice = new_choice
                        break
                else:
                    # Deterministic fallback to the next available name.
                    for candidate in available:
                        if candidate != self._last_enemy_name:
                            choice = candidate
                            break
        self._last_enemy_name = choice
        return choice

    def spawn_random_enemy(self) -> int | None:
        name = self.random_enemy_name()
        if name is None:
            return None
        return self.create_enemy(name)

    def _apply_enemy_scaling(self, enemy_entity: int) -> None:
        tracker_entries = list(self.world.get_component(StoryProgressTracker))
        if not tracker_entries:
            return
        _, tracker = tracker_entries[0]
        if tracker.locations_completed <= 0:
            return
        bonus_hp = tracker.locations_completed * 5
        try:
            health = self.world.component_for_entity(enemy_entity, Health)
        except (KeyError, ValueError):
            return
        # Increase both max and current HP to keep new enemies at full strength.
        health.max_hp += bonus_hp
        health.current = min(health.max_hp, health.current + bonus_hp)

    def _on_request(self, sender, **payload) -> None:
        count = payload.get("count", 1)
        request_id = payload.get("request_id")
        try:
            count_int = int(count)
        except (TypeError, ValueError):
            return
        if count_int <= 0:
            return
        available = self._get_available_enemies()
        choices = list(available)
        self._rng.shuffle(choices)
        offers = choices[:count_int]
        self.event_bus.emit(
            EVENT_ENEMY_POOL_OFFER,
            enemies=offers,
            request_id=request_id,
        )