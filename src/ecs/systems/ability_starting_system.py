"""Legacy wrapper around :class:`AbilityChoiceFlowSystem`."""
from __future__ import annotations

import random
from typing import Callable, Optional

from esper import World

from ecs.events.bus import EventBus
from ecs.systems.ability_choice_flow_system import AbilityChoiceFlowSystem


class AbilityStartingSystem(AbilityChoiceFlowSystem):
    """Backward-compatible entry point for the initial ability draft flow."""

    def __init__(
        self,
        world: World,
        event_bus: EventBus,
        on_selection_complete: Optional[Callable[[], None]] = None,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(
            world,
            event_bus,
            rng=rng,
            on_flow_complete=on_selection_complete,
        )
