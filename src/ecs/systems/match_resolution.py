import random
from typing import List, Tuple, Dict, Set
from esper import World
from ecs.events.bus import (EventBus, EVENT_TILE_SWAP_FINALIZE, EVENT_MATCH_FOUND,
                            EVENT_MATCH_CLEARED, EVENT_GRAVITY_APPLIED, EVENT_REFILL_COMPLETED,
                            EVENT_CASCADE_STEP, EVENT_CASCADE_COMPLETE, EVENT_ANIMATION_START, EVENT_ANIMATION_COMPLETE,
                            EVENT_BOARD_CHANGED)
from ecs.components.active_switch import ActiveSwitch
from ecs.components.tile_type_registry import TileTypeRegistry
from ecs.components.tile_types import TileTypes
from ecs.components.tile import TileType
from ecs.components.board_position import BoardPosition
# Board color mapping deprecated; use TileTypeRegistry
from ecs.components.board import Board

class MatchResolutionSystem:
    def __init__(self, world: World, event_bus: EventBus):
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_TILE_SWAP_FINALIZE, self.on_swap_finalize)
        self.event_bus.subscribe(EVENT_BOARD_CHANGED, self.on_board_changed)
        self.event_bus.subscribe(EVENT_ANIMATION_COMPLETE, self.on_animation_complete)
        self.pending_match_positions: List[Tuple[int,int]] = []
        self.cascade_depth = 0
        self.cascade_active = False

    def on_swap_finalize(self, sender, **kwargs):
        # After a logical swap, initiate resolution sequence
        self._initiate_resolution_if_matches(reason="swap")

    def on_board_changed(self, sender, **kwargs):
        # Triggered after ability effects (or other board-altering events). Run same pipeline.
        reason = kwargs.get("reason", "board_changed")
        # Avoid double-start if a cascade already active; allow ability to start fresh when idle.
        if self.cascade_active:
            return
        self._initiate_resolution_if_matches(reason=reason)

    def _initiate_resolution_if_matches(self, reason: str):
        matches = self.find_all_matches()
        if not matches:
            if self.cascade_active:
                self.event_bus.emit(EVENT_CASCADE_COMPLETE, depth=self.cascade_depth)
            return
        flat_positions = sorted({pos for group in matches for pos in group})
        self.pending_match_positions = flat_positions
        self.event_bus.emit(EVENT_MATCH_FOUND, positions=flat_positions, size=len(flat_positions), reason=reason)
        self.event_bus.emit(EVENT_ANIMATION_START, kind='fade', items=flat_positions)
        self.cascade_depth = 1
        self.cascade_active = True
        self.event_bus.emit(EVENT_CASCADE_STEP, depth=self.cascade_depth, positions=flat_positions, reason=reason)

    def on_animation_complete(self, sender, **kwargs):
        kind = kwargs.get('kind')
        items = kwargs.get('items', [])
        if kind == 'fade':
            positions = items or self.pending_match_positions
            self._after_fade(positions)
        elif kind == 'fall':
            self._after_fall(items)
        elif kind == 'refill':
            self._after_refill()

    def _after_fade(self, positions):
        if not positions:
            return
        # Deterministic ordering for events/tests
        positions = sorted(positions)
        # Capture tile type names prior to clearing (render system derives colors on demand)
        types_before = []  # list of (r,c,type_name) for logic consumers (bank, stats)
        registry = self._registry()
        for (r,c) in positions:
            ent = self._get_entity_at(r,c)
            if ent is None:
                continue
            try:
                sw: ActiveSwitch = self.world.component_for_entity(ent, ActiveSwitch)
                if sw.active:
                    tt: TileType = self.world.component_for_entity(ent, TileType)
                    types_before.append((r,c, tt.type_name))
            except Exception:
                pass
        # Now clear logically
        self.clear_positions(positions)
        owner_entity = self._active_owner()
        # Emit match cleared with type info only; colors are derived in RenderSystem.
        self.event_bus.emit(EVENT_MATCH_CLEARED, positions=positions, types=types_before, owner_entity=owner_entity)
        # Gravity
        moves, cascades = self.compute_gravity_moves()
        if moves:
            self.apply_gravity_moves(moves)
            self.event_bus.emit(EVENT_GRAVITY_APPLIED, cascades=cascades)
            self.event_bus.emit(EVENT_ANIMATION_START, kind='fall', items=moves)
        else:
            self.event_bus.emit(EVENT_GRAVITY_APPLIED, cascades=0)
            new_tiles = self.refill()
            if new_tiles:
                self.event_bus.emit(EVENT_REFILL_COMPLETED, new_tiles=new_tiles)
                self.event_bus.emit(EVENT_ANIMATION_START, kind='refill', items=new_tiles)

    def _after_fall(self, items):
        new_tiles = self.refill()
        if new_tiles:
            self.event_bus.emit(EVENT_REFILL_COMPLETED, new_tiles=new_tiles)
            self.event_bus.emit(EVENT_ANIMATION_START, kind='refill', items=new_tiles)

    def _after_refill(self):
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
        self.event_bus.emit(EVENT_ANIMATION_START, kind='fade', items=flat_positions)

    def board_map(self) -> Dict[Tuple[int,int], str]:
        mapping: Dict[Tuple[int,int], str] = {}
        for ent, pos in self.world.get_component(BoardPosition):
            try:
                sw: ActiveSwitch = self.world.component_for_entity(ent, ActiveSwitch)
            except KeyError:
                continue
            if not sw.active:
                continue
            try:
                tt: TileType = self.world.component_for_entity(ent, TileType)
            except KeyError:
                continue
            mapping[(pos.row, pos.col)] = tt.type_name
        return mapping

    def find_all_matches(self) -> List[List[Tuple[int,int]]]:
        types = self.board_map()
        matches: List[List[Tuple[int,int]]] = []
        # Horizontal scans
        board_comp = self._board()
        for r in range(board_comp.rows):
            run: List[Tuple[int,int]] = []
            last_type = None
            for c in range(board_comp.cols):
                tval = types.get((r,c))
                if tval is not None and tval == last_type:
                    run.append((r,c))
                else:
                    if len(run) >= 3:
                        matches.append(run.copy())
                    run = [(r,c)] if tval is not None else []
                    last_type = tval
            if len(run) >= 3:
                matches.append(run.copy())
        # Vertical scans
        for c in range(board_comp.cols):
            run = []
            last_type = None
            for r in range(board_comp.rows):
                tval = types.get((r,c))
                if tval is not None and tval == last_type:
                    run.append((r,c))
                else:
                    if len(run) >= 3:
                        matches.append(run.copy())
                    run = [(r,c)] if tval is not None else []
                    last_type = tval
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
        for pos in positions:
            ent = self._get_entity_at(*pos)
            if ent is None:
                continue
            try:
                sw: ActiveSwitch = self.world.component_for_entity(ent, ActiveSwitch)
                sw.active = False
            except KeyError:
                continue

    def compute_gravity_moves(self) -> Tuple[List[Dict], int]:
        board_comp = self._board()
        moves: List[Dict] = []
        cascades = 0
        registry = self._registry()
        for c in range(board_comp.cols):
            filled_rows: List[int] = []
            for r in range(board_comp.rows):
                ent = self._get_entity_at(r, c)
                if ent is None:
                    continue
                try:
                    sw: ActiveSwitch = self.world.component_for_entity(ent, ActiveSwitch)
                except KeyError:
                    continue
                if sw.active:
                    filled_rows.append(r)
            for target_index, original_row in enumerate(filled_rows):
                if original_row != target_index:
                    src_ent = self._get_entity_at(original_row, c)
                    dst_ent = self._get_entity_at(target_index, c)
                    if src_ent is None or dst_ent is None:
                        continue
                    src_sw: ActiveSwitch = self.world.component_for_entity(src_ent, ActiveSwitch)
                    if not src_sw.active:
                        continue
                    src_tt: TileType = self.world.component_for_entity(src_ent, TileType)
                    moves.append({'from': (original_row, c), 'to': (target_index, c), 'type_name': src_tt.type_name})
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
            src_sw: ActiveSwitch = self.world.component_for_entity(src_ent, ActiveSwitch)
            dst_sw: ActiveSwitch = self.world.component_for_entity(dst_ent, ActiveSwitch)
            if not src_sw.active:
                continue
            src_tt: TileType = self.world.component_for_entity(src_ent, TileType)
            dst_tt: TileType = self.world.component_for_entity(dst_ent, TileType)
            dst_tt.type_name = src_tt.type_name
            dst_sw.active = True
            src_sw.active = False

    def refill(self) -> List[Tuple[int,int]]:
        spawned = []
        registry = self._registry()
        all_types = registry.all_types()
        for ent, pos in self.world.get_component(BoardPosition):
            try:
                sw: ActiveSwitch = self.world.component_for_entity(ent, ActiveSwitch)
            except KeyError:
                continue
            if not sw.active:
                tt: TileType = self.world.component_for_entity(ent, TileType)
                tt.type_name = random.choice(all_types)
                sw.active = True
                spawned.append((pos.row, pos.col))
        return spawned

    def _registry(self) -> TileTypes:
        for ent, _ in self.world.get_component(TileTypeRegistry):
            return self.world.component_for_entity(ent, TileTypes)
        raise RuntimeError('TileTypes definitions not found')

    def _get_entity_at(self, row: int, col: int):
        for ent, pos in self.world.get_component(BoardPosition):
            if pos.row == row and pos.col == col:
                return ent
        return None

    def _active_owner(self):
        from ecs.components.active_turn import ActiveTurn
        active = list(self.world.get_component(ActiveTurn))
        if not active:
            return None
        return active[0][1].owner_entity

    def _board(self) -> Board:
        # Assume single Board component
        for ent, board in self.world.get_component(Board):
            return board
        raise RuntimeError('Board component not found')