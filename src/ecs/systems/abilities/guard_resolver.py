from __future__ import annotations

import random
from typing import Iterable, List

from esper import World

from ecs.components.active_switch import ActiveSwitch
from ecs.components.board_position import BoardPosition
from ecs.components.tile_status_overlay import TileStatusOverlay
from ecs.events.bus import EVENT_ABILITY_EFFECT_APPLIED, EVENT_CASCADE_COMPLETE, EVENT_EFFECT_APPLY
from ecs.systems.abilities.base import AbilityContext, AbilityResolver
from ecs.systems.turn_state_utils import get_or_create_turn_state


class GuardResolver(AbilityResolver):
    """Resolver for the Mastiffs' guard ability."""

    name = "guard"

    def resolve(self, ctx: AbilityContext) -> None:  # pragma: no cover - exercised via integration tests
        tiles = self._available_tiles(ctx.world)
        if not tiles:
            self._finalize(ctx, [])
            return
        rng = getattr(ctx.world, "random", None)
        generator = rng if isinstance(rng, random.Random) else random.Random()
        if len(tiles) > 5:
            chosen = generator.sample(tiles, 5)
        else:
            chosen = tiles
        affected: List[int] = []
        for tile_entity in chosen:
            affected.append(tile_entity)
            ctx.event_bus.emit(
                EVENT_EFFECT_APPLY,
                owner_entity=tile_entity,
                source_entity=ctx.ability_entity,
                slug="tile_guarded",
                metadata={
                    "source_owner": ctx.owner_entity,
                    "reason": "guard",
                },
            )
        self._finalize(ctx, affected)

    def _available_tiles(self, world: World) -> List[int]:
        candidates: List[int] = []
        for entity, _ in world.get_component(BoardPosition):
            try:
                switch: ActiveSwitch = world.component_for_entity(entity, ActiveSwitch)
            except KeyError:
                continue
            if not switch.active:
                continue
            if self._has_overlay(world, entity):
                continue
            candidates.append(entity)
        return candidates

    @staticmethod
    def _has_overlay(world: World, entity: int) -> bool:
        try:
            world.component_for_entity(entity, TileStatusOverlay)
        except KeyError:
            return False
        return True

    def _finalize(self, ctx: AbilityContext, affected: Iterable[int]) -> None:
        ctx.event_bus.emit(
            EVENT_ABILITY_EFFECT_APPLIED,
            ability_entity=ctx.ability_entity,
            affected=list(affected),
        )
        state = get_or_create_turn_state(ctx.world)
        if not state.cascade_observed:
            ctx.event_bus.emit(EVENT_CASCADE_COMPLETE, depth=0)
