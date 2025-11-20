from __future__ import annotations

from typing import List, Tuple

from esper import World

from ecs.components.active_switch import ActiveSwitch
from ecs.components.effect import Effect
from ecs.components.health import Health
from ecs.components.human_agent import HumanAgent
from ecs.components.tile import TileType
from ecs.events.bus import (
    EVENT_ABILITY_EFFECT_APPLIED,
    EVENT_ANIMATION_START,
    EVENT_BOARD_CHANGED,
    EVENT_CASCADE_COMPLETE,
    EVENT_EFFECT_APPLIED,
    EVENT_EFFECT_REFRESHED,
    EVENT_EFFECT_REMOVE,
    EVENT_EFFECT_APPLY,
    EVENT_TILE_BANK_GAINED,
    EventBus,
)
from ecs.systems.board_ops import GravityMove, clear_tiles_with_cascade, get_entity_at
from ecs.systems.turn_state_utils import get_or_create_turn_state

Position = Tuple[int, int]


class TileSacrificeEffectSystem:
    """Resolves tile_sacrifice effects by removing tiles and granting rewards."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_EFFECT_APPLIED, self._on_effect_event)
        self.event_bus.subscribe(EVENT_EFFECT_REFRESHED, self._on_effect_event)

    def _on_effect_event(self, sender, **payload) -> None:
        if payload.get("slug") != "tile_sacrifice":
            return
        effect_entity = payload.get("effect_entity")
        if effect_entity is None:
            return
        try:
            effect = self.world.component_for_entity(effect_entity, Effect)
        except KeyError:
            return
        metadata = effect.metadata or {}
        row = metadata.get("origin_row")
        col = metadata.get("origin_col")
        if row is None or col is None:
            self._remove_effect(effect_entity, reason="no_target")
            return

        multiplier = self._coerce_int(metadata.get("multiplier"), default=3)
        source_owner = metadata.get("source_owner")
        tile_info = self._tile_at(row, col)
        if tile_info is None:
            self._remove_effect(effect_entity, reason="missing_tile")
            return
        tile_entity, tile_type = tile_info

        if source_owner is not None and multiplier > 0:
            self._grant_rewards(int(source_owner), tile_type, multiplier)

        refill_requested = bool(metadata.get("refill", False))

        colored, _, gravity_moves, cascades, new_tiles = clear_tiles_with_cascade(
            self.world,
            [(int(row), int(col))],
            refill=refill_requested,
        )
        positions = [(entry[0], entry[1]) for entry in colored]
        ability_entity = effect.source_entity
        if ability_entity is not None:
            self.event_bus.emit(
                EVENT_ABILITY_EFFECT_APPLIED,
                ability_entity=ability_entity,
                affected=positions,
            )

        reason = str(metadata.get("reason", effect.slug))
        state = get_or_create_turn_state(self.world)
        triggered_animation = False

        if positions:
            self.event_bus.emit(
                EVENT_BOARD_CHANGED,
                reason=reason,
                positions=positions,
                new_tiles=new_tiles,
                gravity_moves=gravity_moves,
                allow_refill=refill_requested,
            )
            if gravity_moves:
                self.event_bus.emit(
                    EVENT_ANIMATION_START,
                    kind="fall",
                    items=self._serialize_gravity_moves(gravity_moves),
                )
                triggered_animation = True
                state.cascade_active = True
                state.cascade_observed = True
                if cascades > state.cascade_depth:
                    state.cascade_depth = cascades

        if not triggered_animation:
            if not state.cascade_observed:
                self.event_bus.emit(
                    EVENT_CASCADE_COMPLETE,
                    depth=0,
                    source=reason,
                )

        self._remove_effect(effect_entity, reason="resolved")

    def _tile_at(self, row: int, col: int) -> Tuple[int, TileType] | None:
        tile_entity = get_entity_at(self.world, int(row), int(col))
        if tile_entity is None:
            return None
        try:
            switch: ActiveSwitch = self.world.component_for_entity(tile_entity, ActiveSwitch)
            if not switch.active:
                return None
            tile = self.world.component_for_entity(tile_entity, TileType)
        except KeyError:
            return None
        return tile_entity, tile

    def _grant_rewards(self, owner: int, tile: TileType, multiplier: int) -> None:
        amount = max(0, multiplier)
        if amount == 0:
            return
        tile_type = tile.type_name
        self.event_bus.emit(
            EVENT_TILE_BANK_GAINED,
            owner_entity=owner,
            type_name=tile_type,
            amount=amount,
        )
        if tile_type == "witchfire":
            self._emit_witchfire_damage(owner, amount)
        elif tile_type == "chaos":
            self._emit_chaos_damage(owner, amount)

    def _emit_witchfire_damage(self, owner: int, amount: int) -> None:
        for entity, _ in self.world.get_component(Health):
            if entity == owner:
                continue
            self.event_bus.emit(
                EVENT_EFFECT_APPLY,
                owner_entity=entity,
                source_entity=None,
                slug="damage",
                turns=0,
                metadata={
                    "amount": amount,
                    "reason": "witchfire",
                    "source_owner": owner,
                },
            )

    def _emit_chaos_damage(self, owner: int, amount: int) -> None:
        human = self._first_human_entity()
        if human is None:
            return
        self.event_bus.emit(
            EVENT_EFFECT_APPLY,
            owner_entity=human,
            source_entity=None,
            slug="damage",
            turns=0,
            metadata={
                "amount": amount,
                "reason": "chaos",
                "source_owner": owner,
            },
        )

    def _first_human_entity(self) -> int | None:
        for entity, _ in self.world.get_component(HumanAgent):
            return entity
        return None

    def _remove_effect(self, effect_entity: int, *, reason: str) -> None:
        self.event_bus.emit(
            EVENT_EFFECT_REMOVE,
            effect_entity=effect_entity,
            reason=reason,
        )

    @staticmethod
    def _serialize_gravity_moves(moves: List[GravityMove]) -> List[dict]:
        return [
            {"from": move.source, "to": move.target, "type_name": move.type_name}
            for move in moves
        ]

    @staticmethod
    def _coerce_int(value, *, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
