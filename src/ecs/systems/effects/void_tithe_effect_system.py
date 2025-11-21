from __future__ import annotations

from esper import World

from ecs.components.effect import Effect
from ecs.components.effect_list import EffectList
from ecs.components.board_position import BoardPosition
from ecs.components.active_switch import ActiveSwitch
from ecs.events.bus import (
    EVENT_EFFECT_APPLY,
    EVENT_TURN_ADVANCED,
    EventBus,
)
from ecs.utils.combatants import find_primary_opponent


class VoidTitheEffectSystem:
    """Deals damage equal to missing tiles at the end of the owner's turn."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_TURN_ADVANCED, self._on_turn_advanced)

    def _on_turn_advanced(self, sender, **payload) -> None:
        previous_owner = payload.get("previous_owner")
        if previous_owner is None:
            return
        totals = self._collect_effect_totals(int(previous_owner))
        if totals is None:
            return
        multiplier, reason = totals
        missing_tiles = self._missing_tile_count()
        if missing_tiles <= 0:
            return
        damage = missing_tiles * multiplier
        if damage <= 0:
            return
        opponent = self._find_opponent(int(previous_owner))
        if opponent is None:
            return
        self.event_bus.emit(
            EVENT_EFFECT_APPLY,
            owner_entity=opponent,
            source_entity=None,
            slug="damage",
            turns=0,
            metadata={
                "amount": damage,
                "reason": reason,
                "source_owner": previous_owner,
            },
        )

    def _collect_effect_totals(self, owner: int) -> tuple[int, str] | None:
        effect_list = self._effect_list(owner)
        if effect_list is None:
            return None
        multiplier = 0
        reason = "void_tithe"
        found = False
        for effect_id in list(effect_list.effect_entities):
            effect = self._effect(effect_id)
            if effect is None or effect.slug != "void_tithe":
                continue
            found = True
            metadata = effect.metadata or {}
            try:
                amount = int(metadata.get("multiplier", 1))
            except (TypeError, ValueError):
                amount = 1
            if amount > 0:
                multiplier += amount
            reason = str(metadata.get("reason", reason))
        if not found or multiplier <= 0:
            return None
        return multiplier, reason

    def _missing_tile_count(self) -> int:
        missing = 0
        for entity, _ in self.world.get_component(BoardPosition):
            try:
                switch: ActiveSwitch = self.world.component_for_entity(entity, ActiveSwitch)
            except KeyError:
                continue
            if not switch.active:
                missing += 1
        return missing

    def _effect_list(self, owner: int) -> EffectList | None:
        try:
            return self.world.component_for_entity(owner, EffectList)
        except KeyError:
            return None

    def _effect(self, entity: int) -> Effect | None:
        try:
            return self.world.component_for_entity(entity, Effect)
        except KeyError:
            return None

    def _find_opponent(self, owner: int) -> int | None:
        return find_primary_opponent(self.world, owner)
