from __future__ import annotations

import random
import math
from typing import Dict, List, Sequence

from esper import World

from ecs.events.bus import (
    EVENT_SKILL_POOL_OFFER,
    EVENT_SKILL_POOL_REQUEST,
    EventBus,
)
from ecs.components.affinity import Affinity
from ecs.components.skill import Skill
from ecs.factories.skills import available_player_skill_names, create_skill_by_name, discover_player_skill_names
from ecs.utils.affinity_math import (
    affinity_distance,
    combine_affinity_maps,
    normalize_affinity_map,
)


class SkillPoolSystem:
    """Serves skill offers drawn from the pool of player skills."""

    def __init__(self, world: World, event_bus: EventBus, *, rng: random.Random | None = None) -> None:
        self.world = world
        self.event_bus = event_bus
        self._skill_names: Sequence[str] = discover_player_skill_names()
        candidate_rng = rng or getattr(world, "random", None)
        self._rng: random.Random = candidate_rng or random.SystemRandom()
        self._skill_vector_cache: Dict[str, Dict[str, float]] = {}
        self.event_bus.subscribe(EVENT_SKILL_POOL_REQUEST, self._on_pool_request)

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
        available = available_player_skill_names(self.world, owner_entity)
        pool = list(available)
        offers = self._weighted_sample(owner_entity, pool, count_int)
        self.event_bus.emit(
            EVENT_SKILL_POOL_OFFER,
            owner_entity=owner_entity,
            skills=offers,
            request_id=request_id,
        )

    def known_skill_names(self) -> Sequence[str]:
        return self._skill_names

    # ------------------------------------------------------------------
    # Affinity helpers
    # ------------------------------------------------------------------

    def _player_affinity_vector(self, owner_entity: int) -> Dict[str, float]:
        try:
            affinity = self.world.component_for_entity(owner_entity, Affinity)
        except KeyError:
            return {}
        return normalize_affinity_map(affinity.totals)

    def _skill_vector_for_name(self, skill_name: str) -> Dict[str, float]:
        cached = self._skill_vector_cache.get(skill_name)
        if cached is not None:
            return cached
        skill_entity = create_skill_by_name(self.world, skill_name)
        try:
            skill = self.world.component_for_entity(skill_entity, Skill)
        except KeyError:
            vector: Dict[str, float] = {}
        else:
            combined = combine_affinity_maps(getattr(skill, "affinity_bonus", None))
            vector = normalize_affinity_map(combined)
        finally:
            try:
                self.world.delete_entity(skill_entity, immediate=True)
            except Exception:
                self.world.delete_entity(skill_entity)
        self._skill_vector_cache[skill_name] = vector
        return vector

    def _distance_to_weight(self, distance: float) -> float:
        if not math.isfinite(distance):
            return 0.0
        return math.exp(-distance)

    def _weighted_sample(self, owner_entity: int, skill_names: List[str], count: int) -> List[str]:
        if not skill_names or count <= 0:
            return []
        player_vector = self._player_affinity_vector(owner_entity)
        pool: List[tuple[str, float]] = []
        for name in skill_names:
            skill_vector = self._skill_vector_for_name(name)
            distance = affinity_distance(player_vector, skill_vector)
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
