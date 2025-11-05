import random
from typing import List, Optional, Tuple
from esper import World
from ecs.events.bus import EventBus, EVENT_TILE_CLICK, EVENT_TILE_SELECTED, EVENT_TILE_DESELECTED, EVENT_TILE_SWAP_REQUEST, EVENT_TILE_SWAP_FINALIZE, EVENT_TILE_SWAP_DO, EVENT_MOUSE_PRESS
from ecs.components.tile import TileType
from ecs.components.board_position import BoardPosition
from ecs.components.targeting_state import TargetingState

# Seven distinct colors -> initial type names (will evolve into domain types later)
COLOR_NAME_MAP = {
    (180, 60, 60): 'red',
    (80, 170, 80): 'green',
    (70, 90, 180): 'blue',
    (200, 190, 80): 'yellow',
    (170, 80, 160): 'magenta',
    (70, 170, 170): 'cyan',
    (200, 130, 60): 'orange',
}
NAME_TO_COLOR = {v:k for k,v in COLOR_NAME_MAP.items()}
PALETTE: List[Tuple[int,int,int]] = list(COLOR_NAME_MAP.keys())

from ecs.components.board import Board

class BoardSystem:
    def __init__(self, world: World, event_bus: EventBus, rows: int = 8, cols: int = 8):
        self.world = world
        self.event_bus = event_bus
        # Create a single board entity with Board component
        self.board_entity = self.world.create_entity()
        self.world.add_component(self.board_entity, Board(rows=rows, cols=cols))
        self.selected: Optional[Tuple[int,int]] = None
        self.event_bus.subscribe(EVENT_TILE_CLICK, self.on_tile_click)
        self.event_bus.subscribe(EVENT_TILE_SWAP_DO, self.on_swap_do)
        self.event_bus.subscribe(EVENT_MOUSE_PRESS, self.on_mouse_press)
        self._init_board()

    def _init_board(self):
        board: Board = self.world.component_for_entity(self.board_entity, Board)
        for r in range(board.rows):
            for c in range(board.cols):
                ent = self.world.create_entity()
                self.world.add_component(ent, BoardPosition(row=r, col=c))
                # Choose a color that does not create an immediate horizontal or vertical triple.
                available = PALETTE.copy()
                # Prevent horizontal triple: if last two cells same color, exclude that color.
                if c >= 2:
                    left1 = self._get_color(r, c-1)
                    left2 = self._get_color(r, c-2)
                    if left1 == left2 and left1 in available:
                        available = [clr for clr in available if clr != left1]
                # Prevent vertical triple: if last two rows same color in this column, exclude that color.
                if r >= 2:
                    down1 = self._get_color(r-1, c)
                    down2 = self._get_color(r-2, c)
                    if down1 == down2 and down1 in available:
                        available = [clr for clr in available if clr != down1]
                color = random.choice(available) if available else random.choice(PALETTE)
                type_name = COLOR_NAME_MAP.get(color, 'unknown')
                # Provide raw_color for legacy color-based logic/tests while attaching semantic type
                self.world.add_component(ent, TileType(type_name=type_name, color_name=type_name, raw_color=color))

    def on_tile_click(self, sender, **kwargs):
        row = kwargs.get('row')
        col = kwargs.get('col')
        if row is None or col is None:
            return
        # Ignore normal selection/swaps while in targeting mode
        targeting = list(self.world.get_component(TargetingState))
        if targeting:
            return
        if self.selected is None:
            self.selected = (row, col)
            self.event_bus.emit(EVENT_TILE_SELECTED, row=row, col=col)
        else:
            if self.is_adjacent(self.selected, (row,col)):
                src = self.selected
                dst = (row,col)
                # Emit request for animation system to handle; finalize later
                self.event_bus.emit(EVENT_TILE_SWAP_REQUEST, src=src, dst=dst)
                self.selected = None
            else:
                # Change selection to new tile
                self.selected = (row,col)
                self.event_bus.emit(EVENT_TILE_SELECTED, row=row, col=col)

    @staticmethod
    def is_adjacent(a: Tuple[int,int], b: Tuple[int,int]) -> bool:
        ar, ac = a
        br, bc = b
        return (abs(ar - br) == 1 and ac == bc) or (abs(ac - bc) == 1 and ar == br)

    def swap_tiles(self, a: Tuple[int,int], b: Tuple[int,int]):
        # Swap TileType data between entities at positions a and b (type & color_name together)
        ent_a = self._get_entity_at(*a)
        ent_b = self._get_entity_at(*b)
        if ent_a is None or ent_b is None:
            return
        type_a: TileType = self.world.component_for_entity(ent_a, TileType)
        type_b: TileType = self.world.component_for_entity(ent_b, TileType)
        # Swap all relevant fields so both legacy color logic and new type semantics remain consistent
        type_a.type_name, type_b.type_name = type_b.type_name, type_a.type_name
        type_a.color_name, type_b.color_name = type_b.color_name, type_a.color_name
        type_a.raw_color, type_b.raw_color = type_b.raw_color, type_a.raw_color

    def on_mouse_press(self, sender, **kwargs):
        # Right-click always clears current selection (independent of targeting state)
        # Arcade uses 4 for right mouse button (arcade.MOUSE_BUTTON_RIGHT)
        button = kwargs.get('button')
        if button != 4:
            return
        prev = self.selected
        if prev is not None:
            self.selected = None
            self.event_bus.emit(EVENT_TILE_DESELECTED, reason='right_click', prev_row=prev[0], prev_col=prev[1])

    def on_swap_do(self, sender, **kwargs):
        src = kwargs.get('src')
        dst = kwargs.get('dst')
        if not src or not dst:
            return
        self.swap_tiles(src, dst)
        self.event_bus.emit(EVENT_TILE_SWAP_FINALIZE, src=src, dst=dst)

    def _get_entity_at(self, row: int, col: int):
        for ent, pos in self.world.get_component(BoardPosition):
            if pos.row == row and pos.col == col:
                return ent
        return None

    def _get_color(self, row: int, col: int):
        ent = self._get_entity_at(row, col)
        if ent is None:
            return None
        type_comp: TileType = self.world.component_for_entity(ent, TileType)
        return type_comp.raw_color
