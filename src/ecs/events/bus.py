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
EVENT_TILE_CLICK = "tile_click"       # payload: row, col
EVENT_PLAYER_CLICK = "player_click"   # payload: player_entity=int
EVENT_TILE_SELECTED = "tile_selected" # payload: row, col
EVENT_TILE_DESELECTED = "tile_deselected" # payload: reason=str
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
EVENT_CASCADE_STEP = "cascade_step"               # payload: depth=int, positions=[(r,c),...]
EVENT_CASCADE_COMPLETE = "cascade_complete"       # payload: depth=int
EVENT_ANIMATION_START = "animation_start"         # payload: kind=str, items=list/positions, meta=...
EVENT_ANIMATION_COMPLETE = "animation_complete"   # payload: kind=str, items=list/positions, meta=...
EVENT_TILE_BANK_CHANGED = "tile_bank_changed"     # payload: entity=int, counts=dict
EVENT_TILE_BANK_SPEND_REQUEST = "tile_bank_spend_request"  # payload: entity=int, cost=dict[str,int]
EVENT_TILE_BANK_SPENT = "tile_bank_spent"         # payload: entity=int, cost=dict[str,int]
EVENT_TILE_BANK_INSUFFICIENT = "tile_bank_insufficient"  # payload: entity=int, cost=dict[str,int], missing=dict[str,int]
EVENT_ABILITY_ACTIVATE_REQUEST = "ability_activate_request"  # payload: ability_entity=int, owner_entity=int
EVENT_ABILITY_TARGET_MODE = "ability_target_mode"  # payload: ability_entity=int, owner_entity=int
EVENT_ABILITY_TARGET_SELECTED = "ability_target_selected"  # payload: ability_entity=int, target=(r,c)
EVENT_ABILITY_EXECUTE = "ability_execute"  # payload: ability_entity=int, owner_entity=int|None, pending=PendingAbilityTarget
EVENT_ABILITY_EFFECT_APPLIED = "ability_effect_applied"  # payload: ability_entity=int, affected=list[(r,c)]
EVENT_ABILITY_TARGET_CANCELLED = "ability_target_cancelled"  # payload: ability_entity=int, owner_entity=int, reason=str
EVENT_BOARD_CHANGED = "board_changed"  # payload: reason=str, positions=list[(r,c)]
EVENT_TURN_ADVANCED = "turn_advanced"  # payload: previous_owner=int|None, new_owner=int
EVENT_TURN_ACTION_STARTED = "turn_action_started"  # payload: source=str, owner_entity=int|None, ability_entity=int|None
EVENT_BATTLE_RESOLVED = "battle_resolved"  # payload: attacker_owner=int, defender_owner=int, forward=dict, counter=dict
EVENT_EFFECT_APPLY = "effect_apply"  # payload: owner_entity=int, slug=str, metadata=dict, duration=float|None, ...
EVENT_EFFECT_REMOVE = "effect_remove"  # payload: effect_entity=int|None, owner_entity=int|None, slug=str|None
EVENT_EFFECT_APPLIED = "effect_applied"  # payload: effect_entity=int, owner_entity=int, slug=str
EVENT_EFFECT_REFRESHED = "effect_refreshed"  # payload: effect_entity=int, owner_entity=int, slug=str
EVENT_EFFECT_EXPIRED = "effect_expired"  # payload: effect_entity=int, owner_entity=int, slug=str, reason=str
EVENT_HEALTH_DAMAGE = "health_damage"  # payload: source_owner=int, target_entity=int, amount=int, reason=str
EVENT_HEALTH_HEAL = "health_heal"  # payload: source_owner=int, target_entity=int, amount=int, reason=str
EVENT_HEALTH_CHANGED = "health_changed"  # payload: entity=int, current=int, max_hp=int, delta=int
