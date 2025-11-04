from blinker import Signal
from typing import Dict

class EventBus:
    """Simple event bus leveraging blinker Signal objects."""
    def __init__(self):
        self._signals: Dict[str, Signal] = {}

    def subscribe(self, name: str, fn):
        sig = self._signals.setdefault(name, Signal(name))
        # Use weak=False to retain strong reference to bound methods so systems not kept in a variable still receive events.
        sig.connect(fn, weak=False)

    def emit(self, name: str, **payload):
        sig = self._signals.get(name)
        if sig:
            sig.send(self, **payload)

# Common event names (extend as needed)
EVENT_TICK = "tick"
EVENT_SPAWN = "spawn"
EVENT_TILE_CLICK = "tile_click"       # payload: row, col
EVENT_TILE_SELECTED = "tile_selected" # payload: row, col
EVENT_TILE_SWAP = "tile_swap"         # payload: src=(r,c), dst=(r,c)
EVENT_MOUSE_PRESS = "mouse_press"     # payload: x, y, button
EVENT_TILE_SWAP_REQUEST = "tile_swap_request"  # payload: src=(r,c), dst=(r,c)
EVENT_TILE_SWAP_FINALIZE = "tile_swap_finalize" # payload: src=(r,c), dst=(r,c)
EVENT_TILE_SWAP_DO = "tile_swap_do"             # payload: src=(r,c), dst=(r,c)
EVENT_TILE_SWAP_VALID = "tile_swap_valid"       # payload: src=(r,c), dst=(r,c)
EVENT_TILE_SWAP_INVALID = "tile_swap_invalid"   # payload: src=(r,c), dst=(r,c)
EVENT_MATCH_FOUND = "match_found"               # payload: positions=[(r,c),...], size=int
EVENT_MATCH_CLEARED = "match_cleared"           # payload: positions=[(r,c),...]
EVENT_GRAVITY_APPLIED = "gravity_applied"       # payload: cascades=int
EVENT_REFILL_COMPLETED = "refill_completed"     # payload: new_tiles=[(r,c),...]
EVENT_GRAVITY_MOVES = "gravity_moves"           # payload: moves=[{from:(r,c), to:(r,c), color:(r,g,b)}]
EVENT_GRAVITY_SETTLED = "gravity_settled"       # payload: moves=[{from:(r,c), to:(r,c)}]
EVENT_MATCH_CLEAR_BEGIN = "match_clear_begin"    # payload: positions=[(r,c),...]
EVENT_MATCH_FADE_COMPLETE = "match_fade_complete" # payload: positions=[(r,c),...]
EVENT_REFILL_ANIM_DONE = "refill_anim_done"       # payload: none
EVENT_CASCADE_STEP = "cascade_step"               # payload: depth=int, positions=[(r,c),...]
EVENT_CASCADE_COMPLETE = "cascade_complete"       # payload: depth=int
