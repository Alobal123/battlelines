import random
from typing import List, Tuple, Dict, Set
from esper import World
from ecs.events.bus import (EventBus, EVENT_TILE_SWAP_FINALIZE, EVENT_MATCH_FOUND,
                            EVENT_MATCH_CLEARED, EVENT_GRAVITY_APPLIED, EVENT_REFILL_COMPLETED,
                            EVENT_GRAVITY_MOVES, EVENT_GRAVITY_SETTLED, EVENT_MATCH_CLEAR_BEGIN, EVENT_MATCH_FADE_COMPLETE,
                            EVENT_REFILL_ANIM_DONE, EVENT_CASCADE_STEP, EVENT_CASCADE_COMPLETE)
from ecs.components.tile import BoardCell, TileColor
from ecs.systems.board import PALETTE

class MatchResolutionSystem:
    def __init__(self, world: World, event_bus: EventBus, rows: int = 8, cols: int = 8):
        self.world = world
        self.event_bus = event_bus
        self.rows = rows
        self.cols = cols
        event_bus.subscribe(EVENT_TILE_SWAP_FINALIZE, self.on_swap_finalize)
        event_bus.subscribe(EVENT_MATCH_FADE_COMPLETE, self.on_fade_complete)
        event_bus.subscribe(EVENT_GRAVITY_SETTLED, self.on_gravity_settled)
        event_bus.subscribe(EVENT_REFILL_ANIM_DONE, self.on_refill_anim_done)
        self.pending_match_positions: List[Tuple[int,int]] = []
        self.cascade_depth = 0
        self.cascade_active = False

    def on_swap_finalize(self, sender, **kwargs):
        # After a logical swap, scan for matches; if found, resolve cascade
        matches = self.find_all_matches()
        if not matches:
            # If no initial match, emit cascade complete depth 0 (no chain)
            if self.cascade_active:
                self.event_bus.emit(EVENT_CASCADE_COMPLETE, depth=self.cascade_depth)
            return
        flat_positions = sorted({pos for group in matches for pos in group})
        self.pending_match_positions = flat_positions
        self.event_bus.emit(EVENT_MATCH_FOUND, positions=flat_positions, size=len(flat_positions))
        # Begin clear phase visually (fade) without mutating data yet
        self.event_bus.emit(EVENT_MATCH_CLEAR_BEGIN, positions=flat_positions)
        # Start cascade tracking
        self.cascade_depth = 1
        self.cascade_active = True
        # Emit first cascade step (depth 1)
        self.event_bus.emit(EVENT_CASCADE_STEP, depth=self.cascade_depth, positions=flat_positions)

    def on_fade_complete(self, sender, **kwargs):
        positions = kwargs.get('positions') or self.pending_match_positions
        if not positions:
            return
        # Now clear logically
        self.clear_positions(positions)
        self.event_bus.emit(EVENT_MATCH_CLEARED, positions=positions)
        # Gravity
        moves, cascades = self.compute_gravity_moves()
        if moves:
            self.event_bus.emit(EVENT_GRAVITY_MOVES, moves=moves)
            self.apply_gravity_moves(moves)
            self.event_bus.emit(EVENT_GRAVITY_APPLIED, cascades=cascades)
        else:
            self.event_bus.emit(EVENT_GRAVITY_APPLIED, cascades=0)
        if not moves:
            # No falling, perform immediate refill
            new_tiles = self.refill()
            if new_tiles:
                self.event_bus.emit(EVENT_REFILL_COMPLETED, new_tiles=new_tiles)
            self.event_bus.emit(EVENT_GRAVITY_SETTLED, moves=moves)

    def on_gravity_settled(self, sender, **kwargs):
        moves = kwargs.get('moves', [])
        # If moves existed, perform refill now
        if moves:
            new_tiles = self.refill()
            if new_tiles:
                self.event_bus.emit(EVENT_REFILL_COMPLETED, new_tiles=new_tiles)

    def on_refill_anim_done(self, sender, **kwargs):
        # After refill animation completes, check for next cascade step
        if not self.cascade_active:
            return
        matches = self.find_all_matches()
        if not matches:
            # Cascade ends
            self.event_bus.emit(EVENT_CASCADE_COMPLETE, depth=self.cascade_depth)
            self.cascade_active = False
            self.cascade_depth = 0
            return
        flat_positions = sorted({pos for group in matches for pos in group})
        self.pending_match_positions = flat_positions
        self.cascade_depth += 1
        self.event_bus.emit(EVENT_CASCADE_STEP, depth=self.cascade_depth, positions=flat_positions)
        self.event_bus.emit(EVENT_MATCH_FOUND, positions=flat_positions, size=len(flat_positions))
        self.event_bus.emit(EVENT_MATCH_CLEAR_BEGIN, positions=flat_positions)

    def board_map(self) -> Dict[Tuple[int,int], Tuple[int,int,int]]:
        mapping = {}
        for ent, cell in self.world.get_component(BoardCell):
            color_comp = self.world.component_for_entity(ent, TileColor)
            mapping[(cell.row, cell.col)] = color_comp.color
        return mapping

    def find_all_matches(self) -> List[List[Tuple[int,int]]]:
        colors = self.board_map()
        matches: List[List[Tuple[int,int]]] = []
        # Horizontal scans
        for r in range(self.rows):
            run: List[Tuple[int,int]] = []
            last_color = None
            for c in range(self.cols):
                colr = colors.get((r,c))
                if colr is not None and colr == last_color:
                    run.append((r,c))
                else:
                    if len(run) >= 3:
                        matches.append(run.copy())
                    run = [(r,c)] if colr is not None else []
                    last_color = colr
            if len(run) >= 3:
                matches.append(run.copy())
        # Vertical scans
        for c in range(self.cols):
            run = []
            last_color = None
            for r in range(self.rows):
                colr = colors.get((r,c))
                if colr is not None and colr == last_color:
                    run.append((r,c))
                else:
                    if len(run) >= 3:
                        matches.append(run.copy())
                    run = [(r,c)] if colr is not None else []
                    last_color = colr
            if len(run) >= 3:
                matches.append(run.copy())
        # Merge overlapping groups into flat sets then split again (avoid double removal)
        if not matches:
            return []
        # Convert to sets and merge overlaps
        groups = [set(m) for m in matches]
        merged: List[Set[Tuple[int,int]]] = []
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
        return [sorted(list(g)) for g in merged]

    def clear_positions(self, positions: List[Tuple[int,int]]):
        # Remove TileColor component to mark empty (could also remove entity; keep entity for fixed grid indexing)
        for pos in positions:
            ent = self._get_entity_at(*pos)
            if ent is None:
                continue
            # Replace color with None sentinel
            color_comp: TileColor = self.world.component_for_entity(ent, TileColor)
            color_comp.color = None

    def compute_gravity_moves(self) -> Tuple[List[Dict], int]:
        moves: List[Dict] = []
        cascades = 0
        for c in range(self.cols):
            # Gather non-empty rows bottom-up
            filled_rows: List[int] = []
            for r in range(self.rows):  # r=0 bottom
                ent = self._get_entity_at(r, c)
                if ent is None:
                    continue
                color_comp: TileColor = self.world.component_for_entity(ent, TileColor)
                if color_comp.color is not None:
                    filled_rows.append(r)
            # Target rows will be 0..len(filled_rows)-1
            for target_index, original_row in enumerate(filled_rows):
                if original_row != target_index:
                    ent = self._get_entity_at(original_row, c)
                    if ent is None:
                        continue
                    color_comp: TileColor = self.world.component_for_entity(ent, TileColor)
                    moves.append({'from': (original_row, c), 'to': (target_index, c), 'color': color_comp.color})
            if any(m['from'][1] == c for m in moves):
                cascades += 1
        return moves, cascades

    def apply_gravity_moves(self, moves: List[Dict]):
        # Move colors logically; clear sources
        for m in moves:
            src_r, src_c = m['from']
            dst_r, dst_c = m['to']
            src_ent = self._get_entity_at(src_r, src_c)
            dst_ent = self._get_entity_at(dst_r, dst_c)
            if src_ent is None or dst_ent is None:
                continue
            src_color: TileColor = self.world.component_for_entity(src_ent, TileColor)
            dst_color: TileColor = self.world.component_for_entity(dst_ent, TileColor)
            dst_color.color = src_color.color
            src_color.color = None

    def refill(self) -> List[Tuple[int,int]]:
        spawned = []
        for ent, cell in self.world.get_component(BoardCell):
            color_comp: TileColor = self.world.component_for_entity(ent, TileColor)
            if color_comp.color is None:
                color_comp.color = random.choice(PALETTE)
                spawned.append((cell.row, cell.col))
        return spawned

    def _get_entity_at(self, row: int, col: int):
        for ent, cell in self.world.get_component(BoardCell):
            if cell.row == row and cell.col == col:
                return ent
        return None