from __future__ import annotations

import random
from typing import Optional, Tuple

from esper import World

from ecs.components.random_agent import RandomAgent
from ecs.events.bus import EventBus
from ecs.ai.simulation import CloneState
from ecs.systems.base_ai_system import BaseAISystem, OwnerSnapshot, ActionPayload


class RandomAISystem(BaseAISystem):
    """Randomly scores actions but otherwise uses the shared AI shell."""

    def __init__(
        self,
        world: World,
        event_bus: EventBus,
        rng: Optional[random.Random] = None,
    ) -> None:
        super().__init__(world, event_bus, RandomAgent, rng)

    def _score_clone_world(
        self,
        clone_state: CloneState,
        owner_entity: int,
        snapshot: OwnerSnapshot,
        candidate: Tuple[str, ActionPayload],
    ) -> float:
        return self.random.random()

