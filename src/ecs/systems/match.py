from typing import Tuple, List, Set
from ecs.events.bus import EventBus, EVENT_TILE_SWAP_REQUEST, EVENT_TILE_SWAP_VALID, EVENT_TILE_SWAP_INVALID
from ecs.components.tile import BoardCell, TileColor
from esper import World

class MatchSystem:
    def __init__(self, world: World, event_bus: EventBus):
        self.world = world
        self.event_bus = event_bus
        event_bus.subscribe(EVENT_TILE_SWAP_REQUEST, self.on_swap_request)

    def on_swap_request(self, sender, **kwargs):
        src = kwargs.get('src')
        dst = kwargs.get('dst')
        if not src or not dst:
            return
        # Predict match by virtually swapping colors then scanning
        valid = self.creates_match(src, dst)
        if valid:
            self.event_bus.emit(EVENT_TILE_SWAP_VALID, src=src, dst=dst)
        else:
            self.event_bus.emit(EVENT_TILE_SWAP_INVALID, src=src, dst=dst)

    def creates_match(self, a: Tuple[int,int], b: Tuple[int,int]) -> bool:
        # Build map row,col -> color
        grid = {}
        for ent, cell in self.world.get_component(BoardCell):
            color_comp = self.world.component_for_entity(ent, TileColor)
            grid[(cell.row, cell.col)] = color_comp.color
        # Virtually swap
        grid[a], grid[b] = grid[b], grid[a]
        # Check lines containing a or b for any run >=3
        to_check = {a, b}
        for pos in list(to_check):
            if self.has_line_match(grid, pos):
                return True
        return False

    def has_line_match(self, grid: dict, pos: Tuple[int,int]) -> bool:
        row, col = pos
        color = grid.get(pos)
        if color is None:
            return False
        # Horizontal
        h_run = [(row, col)]
        c_left = col-1
        while (row, c_left) in grid and grid[(row, c_left)] == color:
            h_run.append((row, c_left))
            c_left -= 1
        c_right = col+1
        while (row, c_right) in grid and grid[(row, c_right)] == color:
            h_run.append((row, c_right))
            c_right += 1
        if len(h_run) >= 3:
            return True
        # Vertical
        v_run = [(row, col)]
        r_up = row-1
        while (r_up, col) in grid and grid[(r_up, col)] == color:
            v_run.append((r_up, col))
            r_up -= 1
        r_down = row+1
        while (r_down, col) in grid and grid[(r_down, col)] == color:
            v_run.append((r_down, col))
            r_down += 1
        return len(v_run) >= 3
