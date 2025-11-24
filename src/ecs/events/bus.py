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


# ============================================================================
# SYSTEM & TIMING
# ============================================================================
EVENT_TICK = "tick"


# ============================================================================
# INPUT & INTERACTION
# ============================================================================
EVENT_MOUSE_PRESS_RAW = "mouse_press_raw"  # payload: x, y, button, modifiers
EVENT_MOUSE_PRESS = "mouse_press"          # payload: x, y, button
EVENT_MOUSE_MOVE = "mouse_move"            # payload: x, y, dx, dy
EVENT_TILE_CLICK = "tile_click"            # payload: row, col
EVENT_PLAYER_CLICK = "player_click"        # payload: player_entity=int


# ============================================================================
# TILE & BOARD MECHANICS
# ============================================================================
EVENT_TILE_SELECTED = "tile_selected"              # payload: row, col
EVENT_TILE_DESELECTED = "tile_deselected"          # payload: reason=str
EVENT_TILE_SWAP_REQUEST = "tile_swap_request"      # payload: src=(r,c), dst=(r,c)
EVENT_TILE_SWAP_DO = "tile_swap_do"                # payload: src=(r,c), dst=(r,c)
EVENT_TILE_SWAP_FINALIZE = "tile_swap_finalize"    # payload: src=(r,c), dst=(r,c)
EVENT_TILE_SWAP_VALID = "tile_swap_valid"          # payload: src=(r,c), dst=(r,c)
EVENT_TILE_SWAP_INVALID = "tile_swap_invalid"      # payload: src=(r,c), dst=(r,c)
EVENT_MATCH_FOUND = "match_found"                  # payload: positions=[(r,c),...], size=int
EVENT_MATCH_CLEARED = "match_cleared"              # payload: positions=[(r,c),...]
EVENT_GRAVITY_APPLIED = "gravity_applied"          # payload: cascades=int
EVENT_REFILL_COMPLETED = "refill_completed"        # payload: new_tiles=[(r,c),...]
EVENT_CASCADE_STEP = "cascade_step"                # payload: depth=int, positions=[(r,c),...]
EVENT_CASCADE_COMPLETE = "cascade_complete"        # payload: depth=int
EVENT_BOARD_CHANGED = "board_changed"              # payload: reason=str, positions=list[(r,c)]


# ============================================================================
# ANIMATION
# ============================================================================
EVENT_ANIMATION_START = "animation_start"          # payload: kind=str, items=list/positions, meta=...
EVENT_ANIMATION_COMPLETE = "animation_complete"    # payload: kind=str, items=list/positions, meta=...


# ============================================================================
# RESOURCES & MANA
# ============================================================================
EVENT_TILE_BANK_CHANGED = "tile_bank_changed"                # payload: entity=int, counts=dict
EVENT_TILE_BANK_GAINED = "tile_bank_gained"                  # payload: owner_entity=int, type_name=str, amount=int
EVENT_TILE_BANK_SPEND_REQUEST = "tile_bank_spend_request"    # payload: entity=int, cost=dict[str,int]
EVENT_TILE_BANK_SPENT = "tile_bank_spent"                    # payload: entity=int, cost=dict[str,int]
EVENT_TILE_BANK_INSUFFICIENT = "tile_bank_insufficient"      # payload: entity=int, cost=dict[str,int], missing=dict[str,int]
EVENT_TILE_BANK_DEPLETED = "tile_bank_depleted"              # payload: entity=int, owner_entity=int, deltas=dict[str,int]
EVENT_FORBIDDEN_KNOWLEDGE_CHANGED = "forbidden_knowledge_changed"  # payload: entity=int, value=int, max_value=int, delta=int
EVENT_MANA_DRAIN = "mana_drain"                              # payload: source_owner=int|None, target_entity=int, amount=int, reason=str, breakdown=dict, gained=dict


# ============================================================================
# ABILITIES
# ============================================================================
EVENT_ABILITY_ACTIVATE_REQUEST = "ability_activate_request"    # payload: ability_entity=int, owner_entity=int
EVENT_ABILITY_TARGET_MODE = "ability_target_mode"              # payload: ability_entity=int, owner_entity=int
EVENT_ABILITY_TARGET_SELECTED = "ability_target_selected"      # payload: ability_entity=int, target=(r,c)
EVENT_ABILITY_TARGET_CANCELLED = "ability_target_cancelled"    # payload: ability_entity=int, owner_entity=int, reason=str
EVENT_ABILITY_EXECUTE = "ability_execute"                      # payload: ability_entity=int, owner_entity=int|None, pending=PendingAbilityTarget
EVENT_ABILITY_EFFECT_APPLIED = "ability_effect_applied"        # payload: ability_entity=int, affected=list[(r,c)]
EVENT_ABILITY_POOL_REQUEST = "ability_pool_request"            # payload: owner_entity=int, count=int, request_id=Any
EVENT_ABILITY_POOL_OFFER = "ability_pool_offer"                # payload: owner_entity=int, abilities=list[str], request_id=Any
EVENT_ABILITY_CHOICE_GRANTED = "ability_choice_granted"        # payload: owner_entity=int, ability_entity=int, ability_name=str
EVENT_ABILITY_UNLOCKED = "ability_unlocked"                    # payload: ability_name=str


# ============================================================================
# SKILLS
# ============================================================================
EVENT_SKILL_POOL_REQUEST = "skill_pool_request"        # payload: owner_entity=int, count=int, request_id=Any
EVENT_SKILL_POOL_OFFER = "skill_pool_offer"            # payload: owner_entity=int, skills=list[str], request_id=Any
EVENT_SKILL_CHOICE_GRANTED = "skill_choice_granted"    # payload: owner_entity=int, skill_entity=int, skill_name=str
EVENT_SKILL_GAINED = "skill_gained"                    # payload: skill_name=str


# ============================================================================
# ENEMIES & LOCATIONS
# ============================================================================
EVENT_ENEMY_POOL_REQUEST = "enemy_pool_request"        # payload: count=int, request_id=Any
EVENT_ENEMY_POOL_OFFER = "enemy_pool_offer"            # payload: enemies=list[str], request_id=Any
EVENT_LOCATION_POOL_REQUEST = "location_pool_request"  # payload: count=int, request_id=Any
EVENT_LOCATION_POOL_OFFER = "location_pool_offer"      # payload: locations=list[str], request_id=Any
EVENT_LOCATION_CHOICE_GRANTED = "location_choice_granted"  # payload: owner_entity=int, location_slug=str
EVENT_LOCATION_ENTERED = "location_entered"            # payload: location_name=str
EVENT_LOCATION_COMPLETED = "location_completed"        # payload: location_slug=str, enemies_defeated=int


# ============================================================================
# EFFECTS & STATUS
# ============================================================================
EVENT_EFFECT_APPLY = "effect_apply"            # payload: owner_entity=int, slug=str, metadata=dict, duration=float|None, ...
EVENT_EFFECT_APPLIED = "effect_applied"        # payload: effect_entity=int, owner_entity=int, slug=str
EVENT_EFFECT_REFRESHED = "effect_refreshed"    # payload: effect_entity=int, owner_entity=int, slug=str
EVENT_EFFECT_REMOVE = "effect_remove"          # payload: effect_entity=int|None, owner_entity=int|None, slug=str|None
EVENT_EFFECT_EXPIRED = "effect_expired"        # payload: effect_entity=int, owner_entity=int, slug=str, reason=str
EVENT_AFFINITY_UPDATED = "affinity_updated"    # payload: owner_entity=int, totals=dict[str,int], contributions=dict, breakdown=list


# ============================================================================
# HEALTH & DAMAGE
# ============================================================================
EVENT_HEALTH_DAMAGE = "health_damage"      # payload: source_owner=int, target_entity=int, amount=int, reason=str
EVENT_HEALTH_HEAL = "health_heal"          # payload: source_owner=int, target_entity=int, amount=int, reason=str
EVENT_HEALTH_CHANGED = "health_changed"    # payload: entity=int, current=int, max_hp=int, delta=int


# ============================================================================
# COMBAT & DEFEAT
# ============================================================================
EVENT_BATTLE_RESOLVED = "battle_resolved"      # payload: attacker_owner=int, defender_owner=int, forward=dict, counter=dict
EVENT_ENTITY_DEFEATED = "entity_defeated"      # payload: entity=int, reason=str|None, source_owner=int|None
EVENT_PLAYER_DEFEATED = "player_defeated"      # payload: entity=int
EVENT_ENEMY_DEFEATED = "enemy_defeated"        # payload: entity=int
EVENT_COMBAT_RESET = "combat_reset"            # payload: reason=str|None, defeated_entity=int|None


# ============================================================================
# TURN SYSTEM
# ============================================================================
EVENT_TURN_ADVANCED = "turn_advanced"              # payload: previous_owner=int|None, new_owner=int
EVENT_TURN_ACTION_STARTED = "turn_action_started"  # payload: source=str, owner_entity=int|None, ability_entity=int|None
EVENT_EXTRA_TURN_GRANTED = "extra_turn_granted"    # payload: owner_entity=int


# ============================================================================
# GAME FLOW & STATE
# ============================================================================
EVENT_GAME_MODE_CHANGED = "game_mode_changed"          # payload: previous_mode=GameMode|None, new_mode=GameMode
EVENT_MATCH_SETUP_REQUEST = "match_setup_request"      # payload: owner_entity=int|None, enemy_entity=int|None, reason=str|None
EVENT_MATCH_READY = "match_ready"                      # payload: owner_entity=int, enemy_entity=int|None, resume_mode=GameMode, dialogue_mode=GameMode, fallback_mode=GameMode
EVENT_COMBAT_START_REQUEST = "combat_start_request"    # payload: player_entity=int|None, enemy_entity=int|None, resume_mode=GameMode


# ============================================================================
# DIALOGUE & STORY
# ============================================================================
EVENT_DIALOGUE_START = "dialogue_start"            # payload: left_entity=int, right_entity=int, lines=Iterable[dict]|None, resume_mode=GameMode
EVENT_DIALOGUE_ADVANCE = "dialogue_advance"        # payload: None
EVENT_DIALOGUE_COMPLETED = "dialogue_completed"    # payload: left_entity=int, right_entity=int


# ============================================================================
# MENU & UI
# ============================================================================
EVENT_MENU_NEW_GAME_SELECTED = "menu_new_game_selected"    # payload: None
EVENT_MENU_CONTINUE_SELECTED = "menu_continue_selected"    # payload: None
EVENT_CHOICE_SELECTED = "choice_selected"                  # payload: window_entity=int, choice_entity=int, payload_entity=int|None
EVENT_CHOICE_SKIPPED = "choice_skipped"                    # payload: window_entity=int
