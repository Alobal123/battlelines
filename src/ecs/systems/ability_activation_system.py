from __future__ import annotations

from esper import World

from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_EXECUTE,
    EVENT_TILE_BANK_SPENT,
    EVENT_TURN_ACTION_STARTED,
)


class AbilityActivationSystem:
    """Bridges ability cost payment to ability execution.

    Once the TileBankSystem confirms a spend, this system marks the start of the
    turn action and emits a dedicated execution event containing the pending
    targeting information.
    """

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        event_bus.subscribe(EVENT_TILE_BANK_SPENT, self.on_bank_spent)

    def on_bank_spent(self, sender, **payload) -> None:
        ability_entity = payload.get("ability_entity")
        if ability_entity is None:
            return
        try:
            pending: PendingAbilityTarget = self.world.component_for_entity(
                ability_entity, PendingAbilityTarget
            )
        except KeyError:
            return
        owner_entity = self._resolve_owner_for_ability(
            ability_entity, default=pending.owner_entity
        )
        self.event_bus.emit(
            EVENT_TURN_ACTION_STARTED,
            source="ability",
            ability_entity=ability_entity,
            owner_entity=owner_entity,
        )
        self.event_bus.emit(
            EVENT_ABILITY_EXECUTE,
            ability_entity=ability_entity,
            owner_entity=owner_entity,
            pending=pending,
        )

    def _resolve_owner_for_ability(
        self, ability_entity: int, *, default: int | None = None
    ) -> int | None:
        from ecs.components.ability_list_owner import AbilityListOwner

        for owner_ent, owner_comp in self.world.get_component(AbilityListOwner):
            if ability_entity in owner_comp.ability_entities:
                return owner_ent
        return default
