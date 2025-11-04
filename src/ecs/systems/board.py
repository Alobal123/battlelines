import random
from typing import List, Optional, Tuple
from esper import World
from ecs.events.bus import EventBus, EVENT_TILE_CLICK, EVENT_TILE_SELECTED, EVENT_TILE_SWAP_REQUEST, EVENT_TILE_SWAP_FINALIZE, EVENT_TILE_SWAP_DO
from ecs.components.tile import TileColor
from ecs.components.board_position import BoardPosition

# Seven distinct colors
PALETTE: List[Tuple[int,int,int]] = [
    (180, 60, 60),   # muted red
    (80, 170, 80),   # muted green
    (70, 90, 180),   # muted blue
    (200, 190, 80),  # muted yellow
    (170, 80, 160),  # muted magenta
    (70, 170, 170),  # muted cyan
    (200, 130, 60),  # muted orange
]

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
                self.world.add_component(ent, TileColor(color))

    def on_tile_click(self, sender, **kwargs):
        row = kwargs.get('row')
        col = kwargs.get('col')
        if row is None or col is None:
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
        # Swap TileColor data between entities at positions a and b
        ent_a = self._get_entity_at(*a)
        ent_b = self._get_entity_at(*b)
        if ent_a is None or ent_b is None:
            return
        color_a: TileColor = self.world.component_for_entity(ent_a, TileColor)
        color_b: TileColor = self.world.component_for_entity(ent_b, TileColor)
        color_a.color, color_b.color = color_b.color, color_a.color

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
        color_comp: TileColor = self.world.component_for_entity(ent, TileColor)
        return color_comp.color
