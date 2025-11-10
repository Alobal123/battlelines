from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_EXECUTE,
    EVENT_ABILITY_EFFECT_APPLIED,
)
from ecs.systems.abilities.base import AbilityContext, AbilityResolver
from ecs.systems.abilities.registry import create_resolver_registry


class AbilityResolutionSystem:
    """Executes ability effects once activation signals completion."""

    def __init__(
        self,
        world: World,
        event_bus: EventBus,
        resolvers: dict[str, AbilityResolver] | None = None,
    ) -> None:
        self.world = world
        self.event_bus = event_bus
        self._resolvers = create_resolver_registry(resolvers)
        event_bus.subscribe(EVENT_ABILITY_EXECUTE, self.on_execute)

    def on_execute(self, sender, **payload) -> None:
        ability_entity = payload.get("ability_entity")
        if ability_entity is None:
            return
        owner_entity = payload.get("owner_entity")
        pending = payload.get("pending")
        if pending is None:
            try:
                pending = self.world.component_for_entity(ability_entity, PendingAbilityTarget)
            except KeyError:
                return
        try:
            ability = self.world.component_for_entity(ability_entity, Ability)
        except KeyError:
            return
        owner_entity = self._resolve_owner_for_ability(
            ability_entity, default=owner_entity or pending.owner_entity
        )
        resolver = self._resolvers.get(ability.name)
        if resolver is None:
            self.event_bus.emit(
                EVENT_ABILITY_EFFECT_APPLIED,
                ability_entity=ability_entity,
                affected=[],
            )
        else:
            context = AbilityContext(
                world=self.world,
                event_bus=self.event_bus,
                ability_entity=ability_entity,
                ability=ability,
                pending=pending,
                owner_entity=owner_entity,
                active_owner=self._get_active_owner(),
            )
            resolver.resolve(context)
        self._clear_pending_target(ability_entity)

    def _resolve_owner_for_ability(
        self, ability_entity: int, *, default: int | None = None
    ) -> int | None:
        from ecs.components.ability_list_owner import AbilityListOwner

        for owner_ent, owner_comp in self.world.get_component(AbilityListOwner):
            if ability_entity in owner_comp.ability_entities:
                return owner_ent
        return default

    def _get_active_owner(self) -> int | None:
        from ecs.components.active_turn import ActiveTurn

        active = list(self.world.get_component(ActiveTurn))
        if not active:
            return None
        return active[0][1].owner_entity

    def _clear_pending_target(self, ability_entity: int) -> None:
        try:
            self.world.remove_component(ability_entity, PendingAbilityTarget)
        except KeyError:
            pass
