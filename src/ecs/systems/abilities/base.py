from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from esper import World

from ecs.components.ability import Ability
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.events.bus import EventBus


@dataclass(slots=True)
class AbilityContext:
    """Execution context shared by ability resolvers."""

    world: World
    event_bus: EventBus
    ability_entity: int
    ability: Ability
    pending: PendingAbilityTarget
    owner_entity: int | None
    active_owner: int | None


class AbilityResolver(Protocol):
    """Interface implemented by concrete ability resolvers."""

    name: str

    def resolve(self, ctx: AbilityContext) -> None:
        ...
