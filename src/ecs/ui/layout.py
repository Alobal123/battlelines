from ecs.constants import GRID_COLS, GRID_ROWS, TILE_SIZE, BOTTOM_MARGIN, BOARD_MAX_WIDTH_PCT, BOARD_MAX_HEIGHT_PCT

def compute_board_geometry(window_width: int, window_height: int):
    """Return (tile_size, start_x, start_y) using same rules as RenderSystem dynamic scaling.

    Keeps input mapping consistent with render scaling. Mirrors logic in RenderSystem._recalculate_tile_size.
    """
    # Compute maximum board area based on percentage caps instead of static reserves.
    max_board_w = window_width * BOARD_MAX_WIDTH_PCT
    max_board_h = (window_height - BOTTOM_MARGIN) * BOARD_MAX_HEIGHT_PCT
    tile_by_w = max_board_w / GRID_COLS
    tile_by_h = max_board_h / GRID_ROWS
    tile_size = int(min(tile_by_w, tile_by_h))
    if tile_size < 20:
        tile_size = 20
    total_width = GRID_COLS * tile_size
    start_x = (window_width - total_width) / 2
    start_y = BOTTOM_MARGIN
    return tile_size, start_x, start_y
