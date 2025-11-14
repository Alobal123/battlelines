from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from esper import World

from ecs.components.board_position import BoardPosition
from ecs.components.active_switch import ActiveSwitch
from ecs.components.tile import TileType
from ecs.components.tile_type_registry import TileTypeRegistry
from ecs.components.tile_types import TileTypes
from ecs.components.board import Board

Position = Tuple[int, int]
ColorEntry = Tuple[int, int, Tuple[int, int, int]]
TypeEntry = Tuple[int, int, str]


@dataclass(slots=True)
class GravityMove:
    source: Position
    target: Position
    type_name: str


def get_tile_registry(world: World) -> TileTypes:
    for entity, _ in world.get_component(TileTypeRegistry):
        return world.component_for_entity(entity, TileTypes)
    raise RuntimeError("TileTypes definitions not found")


def get_entity_at(world: World, row: int, col: int) -> int | None:
    for entity, position in world.get_component(BoardPosition):
        if position.row == row and position.col == col:
            return entity
    return None


def transform_tiles_to_type(world: World, row: int, col: int, target_type: str) -> List[Position]:
    """Convert every active tile that matches the source tile's type to target_type."""
    source_entity = get_entity_at(world, row, col)
    if source_entity is None:
        return []
    source_switch = world.component_for_entity(source_entity, ActiveSwitch)
    if not source_switch.active:
        return []
    source_tile = world.component_for_entity(source_entity, TileType)
    source_type = source_tile.type_name
    affected: List[Position] = []
    for entity, position in world.get_component(BoardPosition):
        tile_switch: ActiveSwitch = world.component_for_entity(entity, ActiveSwitch)
        if not tile_switch.active:
            continue
        tile_type: TileType = world.component_for_entity(entity, TileType)
        if tile_type.type_name == source_type:
            tile_type.type_name = target_type
            affected.append((position.row, position.col))
    return affected


def clear_tiles_with_cascade(world: World, positions: List[Position]):
    """Clear tiles at positions, apply gravity/refill, and return board change metadata."""
    if not positions:
        return [], [], [], 0, []
    registry = get_tile_registry(world)
    colored: List[ColorEntry] = []
    typed: List[TypeEntry] = []
    for row, col in positions:
        entity = get_entity_at(world, row, col)
        if entity is None:
            continue
        tile_switch: ActiveSwitch = world.component_for_entity(entity, ActiveSwitch)
        if not tile_switch.active:
            continue
        tile_type: TileType = world.component_for_entity(entity, TileType)
        colored.append((row, col, registry.background_for(tile_type.type_name)))
        typed.append((row, col, tile_type.type_name))
        tile_switch.active = False
    moves, cascades = compute_gravity_moves(world)
    new_tiles: List[Position] = []
    if moves:
        apply_gravity_moves(world, moves)
    else:
        new_tiles = refill_inactive_tiles(world)
    return colored, typed, moves, cascades, new_tiles


def compute_gravity_moves(world: World) -> Tuple[List[GravityMove], int]:
    board_comp = None
    for _, board in world.get_component(Board):
        board_comp = board
        break
    if board_comp is None:
        return [], 0
    moves: List[GravityMove] = []
    cascades = 0
    for col in range(board_comp.cols):
        filled_rows: List[int] = []
        for row in range(board_comp.rows):
            entity = get_entity_at(world, row, col)
            if entity is None:
                continue
            tile_switch: ActiveSwitch = world.component_for_entity(entity, ActiveSwitch)
            if tile_switch.active:
                filled_rows.append(row)
        for target_index, original_row in enumerate(filled_rows):
            if original_row == target_index:
                continue
            entity = get_entity_at(world, original_row, col)
            if entity is None:
                continue
            tile_switch = world.component_for_entity(entity, ActiveSwitch)
            if not tile_switch.active:
                continue
            tile_type = world.component_for_entity(entity, TileType)
            moves.append(GravityMove(source=(original_row, col), target=(target_index, col), type_name=tile_type.type_name))
        if any(move.source[1] == col for move in moves):
            cascades += 1
    return moves, cascades


def apply_gravity_moves(world: World, moves: List[GravityMove]) -> None:
    for move in moves:
        src_row, src_col = move.source
        dst_row, dst_col = move.target
        src_entity = get_entity_at(world, src_row, src_col)
        dst_entity = get_entity_at(world, dst_row, dst_col)
        if src_entity is None or dst_entity is None:
            continue
        src_switch: ActiveSwitch = world.component_for_entity(src_entity, ActiveSwitch)
        dst_switch: ActiveSwitch = world.component_for_entity(dst_entity, ActiveSwitch)
        if not src_switch.active:
            continue
        src_tile: TileType = world.component_for_entity(src_entity, TileType)
        dst_tile: TileType = world.component_for_entity(dst_entity, TileType)
        dst_tile.type_name = src_tile.type_name
        dst_switch.active = True
        src_switch.active = False


def refill_inactive_tiles(world: World) -> List[Position]:
    spawned: List[Position] = []
    registry = get_tile_registry(world)
    choices = registry.all_types()
    for entity, position in world.get_component(BoardPosition):
        tile_switch: ActiveSwitch = world.component_for_entity(entity, ActiveSwitch)
        if tile_switch.active:
            continue
        tile_type: TileType = world.component_for_entity(entity, TileType)
        tile_type.type_name = random.choice(choices)
        tile_switch.active = True
        spawned.append((position.row, position.col))
    return spawned


def active_tile_type_map(world: World) -> Dict[Position, str]:
    """Return mapping of active tile positions to their type names."""
    mapping: Dict[Position, str] = {}
    for entity, position in world.get_component(BoardPosition):
        try:
            switch: ActiveSwitch = world.component_for_entity(entity, ActiveSwitch)
            if not switch.active:
                continue
            tile: TileType = world.component_for_entity(entity, TileType)
        except KeyError:
            continue
        mapping[(position.row, position.col)] = tile.type_name
    return mapping


def board_dimensions(world: World) -> Tuple[int, int] | None:
    for _, board in world.get_component(Board):
        return board.rows, board.cols
    return None


def find_all_matches(world: World) -> List[List[Position]]:
    """Detect all contiguous horizontal or vertical matches of length >= 3."""
    types = active_tile_type_map(world)
    dims = board_dimensions(world)
    if not dims or not types:
        return []
    rows, cols = dims
    matches: List[List[Position]] = []
    # Horizontal runs
    for r in range(rows):
        run: List[Position] = []
        last_type = None
        for c in range(cols):
            tval = types.get((r, c))
            if tval is not None and tval == last_type:
                run.append((r, c))
            else:
                if len(run) >= 3:
                    matches.append(run.copy())
                run = [(r, c)] if tval is not None else []
                last_type = tval
        if len(run) >= 3:
            matches.append(run.copy())
    # Vertical runs
    for c in range(cols):
        run = []
        last_type = None
        for r in range(rows):
            tval = types.get((r, c))
            if tval is not None and tval == last_type:
                run.append((r, c))
            else:
                if len(run) >= 3:
                    matches.append(run.copy())
                run = [(r, c)] if tval is not None else []
                last_type = tval
        if len(run) >= 3:
            matches.append(run.copy())
    if not matches:
        return []
    groups = [set(m) for m in matches]
    merged: List[Set[Position]] = []
    while groups:
        first = groups.pop()
        changed = True
        while changed:
            changed = False
            for g in groups[:]:
                if first & g:
                    first |= g
                    groups.remove(g)
                    changed = True
        merged.append(first)
    return [sorted(list(group)) for group in merged]
