GRID_ROWS = 7  # updated from 8 -> 7
GRID_COLS = 9  # updated from 8 -> 9
TILE_SIZE = 50
BOTTOM_MARGIN = 20

# Board maximum footprint relative to window (percentage of window width/height).
# The render/layout code will size the board so it does not exceed either percentage.
BOARD_MAX_WIDTH_PCT = 0.55   # 55% of window width
BOARD_MAX_HEIGHT_PCT = 0.65  # 65% of window height (excluding bottom margin)

# Side panel geometry (panels sit left/right of board and consume remaining horizontal space)
# Minimum width fallback when window is very narrow.
SIDE_PANEL_MIN_WIDTH = 240
# Gap between board edge and inner edge of the side column.
SIDE_GAP = 30
# Height of the horizontal bank bar that sits directly above (its bottom aligns to the board top).
BANK_BAR_HEIGHT = 84
# Padding between the bottom of the bank bar and the first ability rectangle.
ABILITY_TOP_PADDING = 8
# Horizontal inner padding inside side panels for ability rectangles.
SIDE_PANEL_INNER_PAD = 12
