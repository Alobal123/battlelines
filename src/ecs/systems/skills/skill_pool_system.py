from __future__ import annotations

import random
from typing import Sequence

from esper import World

from ecs.events.bus import (
    EVENT_SKILL_POOL_OFFER,
    EVENT_SKILL_POOL_REQUEST,
    EventBus,
)
from ecs.factories.skills import available_player_skill_names, discover_player_skill_names


class SkillPoolSystem:
    """Serves skill offers drawn from the pool of player skills."""

    def __init__(self, world: World, event_bus: EventBus, *, rng: random.Random | None = None) -> None:
        self.world = world
        self.event_bus = event_bus
        self._skill_names: Sequence[str] = discover_player_skill_names()
        candidate_rng = rng or getattr(world, "random", None)
        self._rng: random.Random = candidate_rng or random.SystemRandom()
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
        self._rng.shuffle(pool)
        offers = pool[: min(count_int, len(pool))]
        self.event_bus.emit(
            EVENT_SKILL_POOL_OFFER,
            owner_entity=owner_entity,
            skills=offers,
            request_id=request_id,
        )

    def known_skill_names(self) -> Sequence[str]:
        return self._skill_names
