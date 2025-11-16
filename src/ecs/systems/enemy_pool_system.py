from __future__ import annotations

import importlib
import pkgutil
import random
from typing import Dict, Iterable, Sequence

from esper import World

from ecs.events.bus import (
    EventBus,
    EVENT_ENEMY_POOL_OFFER,
    EVENT_ENEMY_POOL_REQUEST,
)


def _discover_enemy_factories() -> Dict[str, callable]:
    builders: Dict[str, callable] = {}
    package_name = "ecs.factories.enemies"
    package = importlib.import_module(package_name)
    for module in _iter_modules(package_name, package):
        for attr_name in dir(module):
            if not attr_name.startswith("create_enemy_"):
                continue
            factory = getattr(module, attr_name)
            if callable(factory):
                enemy_name = attr_name[len("create_enemy_") :]
                builders.setdefault(enemy_name, factory)
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
        self._rng: random.Random = rng or random.SystemRandom()
        self._factories: Dict[str, callable] = _discover_enemy_factories()
        self._names: Sequence[str] = tuple(sorted(self._factories.keys()))
        self.event_bus.subscribe(EVENT_ENEMY_POOL_REQUEST, self._on_request)

    def known_enemy_names(self) -> Sequence[str]:
        return self._names

    def create_enemy(self, name: str) -> int:
        factory = self._factories.get(name)
        if factory is None:
            raise ValueError(f"Unknown enemy '{name}'")
        return factory(self.world)

    def random_enemy_name(self) -> str | None:
        if not self._names:
            return None
        return self._rng.choice(self._names)

    def spawn_random_enemy(self) -> int | None:
        name = self.random_enemy_name()
        if name is None:
            return None
        return self.create_enemy(name)

    def _on_request(self, sender, **payload) -> None:
        count = payload.get("count", 1)
        request_id = payload.get("request_id")
        try:
            count_int = int(count)
        except (TypeError, ValueError):
            return
        if count_int <= 0:
            return
        choices = list(self._names)
        self._rng.shuffle(choices)
        offers = choices[:count_int]
        self.event_bus.emit(
            EVENT_ENEMY_POOL_OFFER,
            enemies=offers,
            request_id=request_id,
        )