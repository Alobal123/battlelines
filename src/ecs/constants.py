GRID_ROWS = 8
GRID_COLS = 8
TILE_SIZE = 64
BOTTOM_MARGIN = 20

# Board maximum footprint relative to window (percentage of window width/height).
# The render/layout code will size the board so it does not exceed either percentage.
BOARD_MAX_WIDTH_PCT = 0.75   # allow board to consume up to 75% of window width
BOARD_MAX_HEIGHT_PCT = 0.90  # allow board to consume up to 90% of window height (excluding bottom margin)

# Side panel geometry (panels sit left/right of board and consume remaining horizontal space)
# Minimum width fallback when window is very narrow.
SIDE_PANEL_MIN_WIDTH = 240
# Gap between board edge and inner edge of the side column.
SIDE_GAP = 30
# Height of the horizontal bank bar that sits directly above (its bottom aligns to the board top).
BANK_BAR_HEIGHT = 68
# Extra breathing space added to bank bar for resource circle + count layout.
BANK_BAR_EXTRA_HEIGHT = 28
# Height of player panel above the bank bar.
PLAYER_PANEL_HEIGHT = 46
# Portrait block inserted between name and bank bars
PLAYER_PORTRAIT_SIZE = 140
PLAYER_PORTRAIT_PADDING = 16  # vertical breathing room below portrait block
# Padding between the bottom of the bank bar and the first ability rectangle.
ABILITY_TOP_PADDING = 8
# Horizontal inner padding inside side panels for ability rectangles.
SIDE_PANEL_INNER_PAD = 12
# Small margin from top of window before side panels start (allows breathing room)
SIDE_PANEL_TOP_MARGIN = 8
