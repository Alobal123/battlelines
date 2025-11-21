from __future__ import annotations

import importlib
import pkgutil
import random
import math
from typing import Dict, List, Sequence, Set

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.affinity import Affinity
from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_POOL_OFFER,
    EVENT_ABILITY_POOL_REQUEST,
)
from ecs.utils.affinity_math import (
    affinity_distance,
    combine_affinity_maps,
    normalize_affinity_map,
)

_BASIC_ABILITY_NAMES: Sequence[str] | None = None


def discover_basic_player_ability_names() -> Sequence[str]:
    """Return the canonical set of basic player ability names."""
    global _BASIC_ABILITY_NAMES
    if _BASIC_ABILITY_NAMES is not None:
        return _BASIC_ABILITY_NAMES

    from ecs.factories import player_abilities as ability_package

    names: Set[str] = set()
    package_name = ability_package.__name__
    package_path = getattr(ability_package, "__path__", None)
    if package_path:
        for module_info in pkgutil.iter_modules(package_path):
            if module_info.name.startswith("__"):
                continue
            module = importlib.import_module(f"{package_name}.{module_info.name}")
            names.update(_extract_ability_names_from_module(module))
    names.update(_extract_ability_names_from_module(ability_package))
    _BASIC_ABILITY_NAMES = tuple(sorted(names))
    return _BASIC_ABILITY_NAMES


def _extract_ability_names_from_module(module) -> Set[str]:
    names: Set[str] = set()
    for attr_name, attr_value in vars(module).items():
        if not attr_name.startswith("create_ability_"):
            continue
        if callable(attr_value):
            ability_name = attr_name[len("create_ability_") :]
            if ability_name:
                names.add(ability_name)
    return names


def owned_basic_player_ability_names(world: World, owner_entity: int) -> Set[str]:
    owned: Set[str] = set()
    try:
        owner = world.component_for_entity(owner_entity, AbilityListOwner)
    except KeyError:
        return owned
    for ability_entity in owner.ability_entities:
        try:
            ability = world.component_for_entity(ability_entity, Ability)
        except KeyError:
            continue
        if ability.name:
            owned.add(ability.name)
    return owned


def available_basic_player_ability_names(world: World, owner_entity: int) -> List[str]:
    ability_names = discover_basic_player_ability_names()
    owned = owned_basic_player_ability_names(world, owner_entity)
    if not owned:
        return list(ability_names)
    return [name for name in ability_names if name not in owned]


class AbilityPoolSystem:
    """Serves ability offers based on the pool of basic player abilities."""

    def __init__(self, world: World, event_bus: EventBus, *, rng: random.Random | None = None) -> None:
        self.world = world
        self.event_bus = event_bus
        self._ability_names: Sequence[str] = discover_basic_player_ability_names()
        candidate_rng = rng or getattr(world, "random", None)
        self._rng: random.Random = candidate_rng or random.SystemRandom()
        self._ability_vector_cache: Dict[str, Dict[str, float]] = {}
        self.event_bus.subscribe(EVENT_ABILITY_POOL_REQUEST, self._on_pool_request)

    def _on_pool_request(self, sender, **payload) -> None:
        owner_entity = payload.get("owner_entity")
        count = payload.get("count")
        request_id = payload.get("request_id")
        if owner_entity is None:
            return
        if count is None:
            return
        try:
            count_int = int(count)
        except (TypeError, ValueError):
            return
        if count_int <= 0:
            return
        available = available_basic_player_ability_names(self.world, owner_entity)
        pool = list(available)
        offers = self._weighted_sample(owner_entity, pool, count_int)
        self.event_bus.emit(
            EVENT_ABILITY_POOL_OFFER,
            owner_entity=owner_entity,
            abilities=offers,
            request_id=request_id,
        )

    def known_ability_names(self) -> Sequence[str]:
        """Expose discovered ability names for tests or debug tooling."""
        return self._ability_names

    # ------------------------------------------------------------------
    # Affinity helpers
    # ------------------------------------------------------------------

    def _player_affinity_vector(self, owner_entity: int) -> Dict[str, float]:
        try:
            affinity = self.world.component_for_entity(owner_entity, Affinity)
        except KeyError:
            return {}
        return normalize_affinity_map(affinity.totals)

    def _ability_vector_for_name(self, ability_name: str) -> Dict[str, float]:
        cached = self._ability_vector_cache.get(ability_name)
        if cached is not None:
            return cached
        from ecs.factories.abilities import create_ability_by_name

        ability_entity = create_ability_by_name(self.world, ability_name)
        try:
            ability = self.world.component_for_entity(ability_entity, Ability)
        except KeyError:
            vector: Dict[str, float] = {}
        else:
            combined = combine_affinity_maps(ability.cost, getattr(ability, "affinity_bonus", None))
            vector = normalize_affinity_map(combined)
        finally:
            try:
                self.world.delete_entity(ability_entity, immediate=True)
            except Exception:
                self.world.delete_entity(ability_entity)
        self._ability_vector_cache[ability_name] = vector
        return vector

    def _distance_to_weight(self, distance: float) -> float:
        if not math.isfinite(distance):
            return 0.0
        return math.exp(-distance)

    def _weighted_sample(self, owner_entity: int, ability_names: List[str], count: int) -> List[str]:
        if not ability_names or count <= 0:
            return []
        player_vector = self._player_affinity_vector(owner_entity)
        pool: List[tuple[str, float]] = []
        for name in ability_names:
            ability_vector = self._ability_vector_for_name(name)
            distance = affinity_distance(player_vector, ability_vector)
            weight = self._distance_to_weight(distance)
            pool.append((name, max(0.0, weight)))
        selections: List[str] = []
        candidates = pool[:]
        picks = min(count, len(candidates))
        for _ in range(picks):
            total_weight = sum(weight for _, weight in candidates)
            if total_weight <= 0:
                idx = int(self._rng.random() * len(candidates))
            else:
                threshold = self._rng.random() * total_weight
                cumulative = 0.0
                idx = len(candidates) - 1
                for candidate_index, (name, weight) in enumerate(candidates):
                    cumulative += weight
                    if cumulative >= threshold:
                        idx = candidate_index
                        break
            name, _ = candidates.pop(idx)
            selections.append(name)
        return selections
