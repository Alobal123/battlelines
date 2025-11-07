from ecs.constants import GRID_COLS, GRID_ROWS, TILE_SIZE, BOTTOM_MARGIN

def compute_board_geometry(window_width: int, window_height: int):
    """Return (tile_size, start_x, start_y) using same rules as RenderSystem dynamic scaling.

    Keeps input mapping consistent with render scaling. Mirrors logic in RenderSystem._recalculate_tile_size.
    """
    ability_panel_w = 160
    side_reserve = ability_panel_w * 2 + 120
    available_w = max(200, window_width - side_reserve)
    vertical_reserve = BOTTOM_MARGIN + 260
    available_h = max(200, window_height - vertical_reserve)
    tile_by_w = available_w / GRID_COLS
    tile_by_h = available_h / GRID_ROWS
    tile_size = int(min(tile_by_w, tile_by_h))
    if tile_size < 20:
        tile_size = 20
    total_width = GRID_COLS * tile_size
    start_x = (window_width - total_width) / 2
    start_y = BOTTOM_MARGIN
    return tile_size, start_x, start_y
