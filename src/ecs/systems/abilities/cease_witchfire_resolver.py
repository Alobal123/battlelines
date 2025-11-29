from __future__ import annotations

import random
from typing import List, Sequence, Tuple

from esper import World

from ecs.components.active_switch import ActiveSwitch
from ecs.components.board_position import BoardPosition
from ecs.components.tile import TileType
from ecs.components.tile_type_registry import TileTypeRegistry
from ecs.components.tile_types import TileTypes
from ecs.events.bus import EVENT_ABILITY_EFFECT_APPLIED, EVENT_CASCADE_COMPLETE
from ecs.systems.abilities.base import (
    AbilityContext,
    AbilityResolver,
    EffectDrivenAbilityResolver,
)
from ecs.systems.turn_state_utils import get_or_create_turn_state

Position = Tuple[int, int]


class CeaseWitchfireResolver(AbilityResolver):
    """Resolver for the Cease Witchfire ability that scrubs witchfire tiles."""

    name = "cease_witchfire"

    def __init__(self) -> None:
        self._effect_helper = EffectDrivenAbilityResolver()

    def resolve(self, ctx: AbilityContext) -> None:  # pragma: no cover - behaviour tested via integration
        positions, target_types = self._plan_transformations(ctx)
        ctx.scratchpad["cease_witchfire_positions"] = [list(pos) for pos in positions]
        ctx.scratchpad["cease_witchfire_target_types"] = target_types

        affected_entities = self._effect_helper._apply_declared_effects(ctx)
        ctx.event_bus.emit(
            EVENT_ABILITY_EFFECT_APPLIED,
            ability_entity=ctx.ability_entity,
            affected=affected_entities,
        )
        state = get_or_create_turn_state(ctx.world)
        if not state.cascade_observed:
            ctx.event_bus.emit(EVENT_CASCADE_COMPLETE, depth=0)

    def _plan_transformations(self, ctx: AbilityContext) -> Tuple[List[Position], List[str]]:
        world = ctx.world
        options = self._spawnable_mana_types(world)
        if not options:
            return [], []

        candidates = self._witchfire_tiles(world)
        if not candidates:
            return [], []

        rng = getattr(world, "random", None)
        generator = rng if isinstance(rng, random.Random) else random.Random()
        if len(candidates) > 3:
            selection = generator.sample(candidates, k=3)
        else:
            selection = candidates

        positions: List[Position] = []
        target_types: List[str] = []
        for entity, position in selection:
            new_type = generator.choice(options)
            row = int(position.row)
            col = int(position.col)
            positions.append((row, col))
            target_types.append(new_type)
        return positions, target_types

    @staticmethod
    def _witchfire_tiles(world: World) -> List[Tuple[int, BoardPosition]]:
        tiles: List[Tuple[int, BoardPosition]] = []
        for entity, position in world.get_component(BoardPosition):
            try:
                switch: ActiveSwitch = world.component_for_entity(entity, ActiveSwitch)
                if not switch.active:
                    continue
                tile: TileType = world.component_for_entity(entity, TileType)
            except KeyError:
                continue
            if tile.type_name == "witchfire":
                tiles.append((entity, position))
        return tiles

    @staticmethod
    def _spawnable_mana_types(world: World) -> Sequence[str]:
        registry_entity = CeaseWitchfireResolver._registry_entity(world)
        if registry_entity is None:
            return ()
        tile_types: TileTypes = world.component_for_entity(registry_entity, TileTypes)
        spawnable = [name for name in tile_types.spawnable_types() if name != "witchfire"]
        if spawnable:
            return tuple(spawnable)
        fallback = [name for name in tile_types.defined_types() if name != "witchfire"]
        return tuple(fallback)

    @staticmethod
    def _registry_entity(world: World) -> int | None:
        for entity, _ in world.get_component(TileTypeRegistry):
            return entity
        return None
