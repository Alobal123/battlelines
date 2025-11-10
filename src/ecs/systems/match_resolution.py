from typing import List, Tuple, Dict, Set
from esper import World
from ecs.events.bus import (EventBus, EVENT_TILE_SWAP_FINALIZE, EVENT_MATCH_FOUND,
                            EVENT_MATCH_CLEARED, EVENT_GRAVITY_APPLIED, EVENT_REFILL_COMPLETED,
                            EVENT_CASCADE_STEP, EVENT_CASCADE_COMPLETE, EVENT_ANIMATION_START, EVENT_ANIMATION_COMPLETE,
                            EVENT_BOARD_CHANGED, EVENT_TURN_ACTION_STARTED)
from ecs.components.active_switch import ActiveSwitch
from ecs.components.tile import TileType
from ecs.components.board_position import BoardPosition
# Board color mapping deprecated; use TileTypeRegistry
from ecs.components.board import Board
from ecs.systems.board_ops import clear_tiles_with_cascade, refill_inactive_tiles
from ecs.systems.turn_state_utils import get_or_create_turn_state

class MatchResolutionSystem:
    def __init__(self, world: World, event_bus: EventBus):
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_TILE_SWAP_FINALIZE, self.on_swap_finalize)
        self.event_bus.subscribe(EVENT_BOARD_CHANGED, self.on_board_changed)
        self.event_bus.subscribe(EVENT_ANIMATION_COMPLETE, self.on_animation_complete)
        self.pending_match_positions: List[Tuple[int, int]] = []

    def on_swap_finalize(self, sender, **kwargs):
        # After a logical swap, initiate resolution sequence
        self.event_bus.emit(
            EVENT_TURN_ACTION_STARTED,
            source="swap",
            owner_entity=self._active_owner(),
        )
        self._initiate_resolution_if_matches(reason="swap")

    def on_board_changed(self, sender, **kwargs):
        # Triggered after ability effects (or other board-altering events). Run same pipeline.
        reason = kwargs.get("reason", "board_changed")
        # Avoid double-start if a cascade already active; allow ability to start fresh when idle.
        state = get_or_create_turn_state(self.world)
        if state.cascade_active:
            return
        self._initiate_resolution_if_matches(reason=reason)

    def _initiate_resolution_if_matches(self, reason: str):
        state = get_or_create_turn_state(self.world)
        matches = self.find_all_matches()
        if not matches:
            if state.cascade_active:
                self.event_bus.emit(EVENT_CASCADE_COMPLETE, depth=state.cascade_depth)
            return
        flat_positions = sorted({pos for group in matches for pos in group})
        self.pending_match_positions = flat_positions
        self.event_bus.emit(EVENT_MATCH_FOUND, positions=flat_positions, size=len(flat_positions), reason=reason)
        self.event_bus.emit(EVENT_ANIMATION_START, kind='fade', items=flat_positions)
        depth = (state.cascade_depth + 1) if state.cascade_active else 1
        self.event_bus.emit(EVENT_CASCADE_STEP, depth=depth, positions=flat_positions, reason=reason)

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
        # Delegate clear/gravity/refill handling to shared board ops to keep behaviour consistent.
        _, typed_before, moves, cascades, new_tiles = clear_tiles_with_cascade(self.world, positions)
        types_before = sorted(typed_before)
        owner_entity = self._active_owner()
        # Emit match cleared with type info only; colors are derived in RenderSystem.
        self.event_bus.emit(EVENT_MATCH_CLEARED, positions=positions, types=types_before, owner_entity=owner_entity)
        # Gravity
        if moves:
            fall_payload = [
                {'from': move.source, 'to': move.target, 'type_name': move.type_name}
                for move in moves
            ]
            self.event_bus.emit(EVENT_GRAVITY_APPLIED, cascades=cascades)
            self.event_bus.emit(EVENT_ANIMATION_START, kind='fall', items=fall_payload)
        else:
            self.event_bus.emit(EVENT_GRAVITY_APPLIED, cascades=0)
            if new_tiles:
                self.event_bus.emit(EVENT_REFILL_COMPLETED, new_tiles=new_tiles)
                self.event_bus.emit(EVENT_ANIMATION_START, kind='refill', items=new_tiles)

    def _after_fall(self, items):
        new_tiles = refill_inactive_tiles(self.world)
        if new_tiles:
            self.event_bus.emit(EVENT_REFILL_COMPLETED, new_tiles=new_tiles)
            self.event_bus.emit(EVENT_ANIMATION_START, kind='refill', items=new_tiles)

    def _after_refill(self):
        # After refill animation completes, check for next cascade step
        state = get_or_create_turn_state(self.world)
        matches = self.find_all_matches()
        if not matches:
            # Cascade ends
            if state.cascade_active:
                self.event_bus.emit(EVENT_CASCADE_COMPLETE, depth=state.cascade_depth)
            return
        flat_positions = sorted({pos for group in matches for pos in group})
        self.pending_match_positions = flat_positions
        if state.cascade_active:
            depth = state.cascade_depth + 1
        else:
            depth = 1
            self.event_bus.emit(
                EVENT_TURN_ACTION_STARTED,
                source="cascade",
                owner_entity=self._active_owner(),
            )
        self.event_bus.emit(EVENT_CASCADE_STEP, depth=depth, positions=flat_positions)
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