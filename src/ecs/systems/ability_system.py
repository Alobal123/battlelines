from esper import World
from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_ACTIVATE_REQUEST,
    EVENT_ABILITY_TARGET_MODE,
    EVENT_ABILITY_TARGET_SELECTED,
    EVENT_ABILITY_EFFECT_APPLIED,
    EVENT_ABILITY_TARGET_CANCELLED,
    EVENT_BOARD_CHANGED,
    EVENT_TILE_BANK_SPEND_REQUEST,
    EVENT_TILE_BANK_SPENT,
    EVENT_TILE_BANK_INSUFFICIENT,
    EVENT_TILE_CLICK,
    EVENT_MOUSE_PRESS,
    EVENT_MATCH_CLEARED,
    EVENT_GRAVITY_APPLIED,
    EVENT_REFILL_COMPLETED,
    EVENT_ANIMATION_START,
)
from ecs.components.ability import Ability
from ecs.components.targeting_state import TargetingState
from ecs.components.board_position import BoardPosition
from ecs.systems.board import NAME_TO_COLOR  # for tactical_shift consistent red mapping
from ecs.components.tile import TileType
from ecs.components.pending_ability_target import PendingAbilityTarget


class AbilitySystem:
    """Ability activation, targeting, and effect application.

    Abilities:
      tactical_shift: Convert all tiles of the selected tile's color to red (255,0,0).
      crimson_pulse: Clear (remove) a 3x3 area centered on the selected tile (set color=None).
    """

    def __init__(self, world: World, event_bus: EventBus):
        self.world = world
        self.event_bus = event_bus
        event_bus.subscribe(EVENT_ABILITY_ACTIVATE_REQUEST, self.on_activate_request)
        # Spend now delayed; we no longer subscribe to immediate spent for targeting.
        event_bus.subscribe(EVENT_TILE_BANK_INSUFFICIENT, self.on_bank_insufficient)
        event_bus.subscribe(EVENT_TILE_CLICK, self.on_tile_click)
        event_bus.subscribe(EVENT_TILE_BANK_SPENT, self.on_bank_spent)
        event_bus.subscribe(EVENT_MOUSE_PRESS, self.on_mouse_press)

    def on_activate_request(self, sender, **payload):
        ability_entity = payload['ability_entity']
        owner_entity = payload['owner_entity']
        # Enter targeting mode first; cost will be spent only after effect applied.
        self.world.add_component(owner_entity, TargetingState(ability_entity=ability_entity))
        self.event_bus.emit(EVENT_ABILITY_TARGET_MODE, ability_entity=ability_entity, owner_entity=owner_entity)

    def on_bank_insufficient(self, sender, **payload):
        return

    def on_tile_click(self, sender, **payload):
        targeting = list(self.world.get_component(TargetingState))
        if not targeting:
            return
        row = payload['row']; col = payload['col']
        owner_entity, targeting_state = targeting[0]
        ability_entity = targeting_state.ability_entity
        # ability_entity should be int; defensive check
        if not isinstance(ability_entity, int):
            return
        ability = self.world.component_for_entity(ability_entity, Ability)
        # Attach pending component to ability entity (or overwrite existing)
        self.world.add_component(ability_entity, PendingAbilityTarget(
            ability_entity=ability_entity,
            owner_entity=owner_entity,
            row=row,
            col=col,
        ))
        # Request spend; do NOT apply effect yet
        self.event_bus.emit(
            EVENT_TILE_BANK_SPEND_REQUEST,
            entity=owner_entity,
            cost=ability.cost,
            ability_entity=ability_entity,
        )
        # Remove targeting state (exit targeting irrespective of success)
        self.world.remove_component(owner_entity, TargetingState)
        # Target selected event can fire now for UI feedback
        self.event_bus.emit(EVENT_ABILITY_TARGET_SELECTED, ability_entity=ability_entity, target=(row, col))

    def on_bank_spent(self, sender, **payload):
        ability_entity = payload.get('ability_entity')
        if ability_entity is None:
            return
        # Retrieve pending target component
        try:
            pending: PendingAbilityTarget = self.world.component_for_entity(ability_entity, PendingAbilityTarget)
        except KeyError:
            return  # No pending target stored
        owner_entity = pending.owner_entity
        row = pending.row; col = pending.col
        ability = self.world.component_for_entity(ability_entity, Ability)
        if ability.name == 'tactical_shift':
            affected = self._apply_transform_all_color_to_target(row, col, ability)
            self.event_bus.emit(EVENT_ABILITY_EFFECT_APPLIED, ability_entity=ability_entity, affected=affected)
            self.event_bus.emit(EVENT_BOARD_CHANGED, reason='ability_effect', positions=affected)
        elif ability.name == 'crimson_pulse':
            positions = self._prepare_crimson_pulse_area(row, col)
            # Clear pipeline will emit board changed etc.
            self._resolve_external_clear(positions)
            self.event_bus.emit(EVENT_ABILITY_EFFECT_APPLIED, ability_entity=ability_entity, affected=positions)
        else:
            self.event_bus.emit(EVENT_ABILITY_EFFECT_APPLIED, ability_entity=ability_entity, affected=[])
        # Remove pending component after applying effect
        self.world.remove_component(ability_entity, PendingAbilityTarget)

    def _apply_transform_all_color_to_target(self, row: int, col: int, ability: Ability):
        """Transform all tiles of the selected tile's original color to the ability's configured target color.

        ability.params['target_color'] may specify a color name present in NAME_TO_COLOR; defaults to 'red'.
        Ensures type_name and color_name match the target color name.
        """
        target_color_name = ability.params.get('target_color', 'red') if hasattr(ability, 'params') else 'red'
        palette_color = NAME_TO_COLOR.get(target_color_name)
        if palette_color is None:
            # Fallback to red if invalid
            target_color_name = 'red'
            palette_color = NAME_TO_COLOR.get('red')
        source_color = None
        for ent, pos in self.world.get_component(BoardPosition):
            if pos.row == row and pos.col == col:
                tile = self.world.component_for_entity(ent, TileType)
                source_color = tile.color
                break
        if source_color is None:
            return []
        affected = []
        for ent, pos in self.world.get_component(BoardPosition):
            tile = self.world.component_for_entity(ent, TileType)
            if tile.color == source_color:
                tile.raw_color = palette_color
                tile.type_name = target_color_name
                tile.color_name = target_color_name
                affected.append((pos.row, pos.col))
        return affected

    def _prepare_crimson_pulse_area(self, row: int, col: int):
        """Return positions in 3x3 area; does not clear yet (clearing done in resolution)."""
        from ecs.components.board import Board
        board_comp = None
        for _, b in self.world.get_component(Board):
            board_comp = b
            break
        rows = board_comp.rows if board_comp else 8
        cols = board_comp.cols if board_comp else 8
        positions = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr = row + dr
                cc = col + dc
                if rr < 0 or cc < 0 or rr >= rows or cc >= cols:
                    continue
                positions.append((rr, cc))
        return positions

    # --- External clear pipeline (crimson pulse) replicating match resolution logic ---
    def _resolve_external_clear(self, positions):
        if not positions:
            return
        # Capture colors prior to clearing
        colored = []
        for (r, c) in positions:
            ent = self._get_entity_at(r, c)
            if ent is None:
                continue
            tile: TileType = self.world.component_for_entity(ent, TileType)
            if tile.color is not None:
                colored.append((r, c, tile.color))
        # Clear
        for (r, c) in positions:
            ent = self._get_entity_at(r, c)
            if ent is None:
                continue
            tile: TileType = self.world.component_for_entity(ent, TileType)
            tile.color = None
        # Emit match cleared analog so TileBankSystem increments
        self.event_bus.emit(EVENT_MATCH_CLEARED, positions=sorted(positions), colors=colored)
        # Apply gravity & refill like MatchResolutionSystem._after_fade
        moves, cascades = self._compute_gravity_moves()
        if moves:
            self._apply_gravity_moves(moves)
            self.event_bus.emit(EVENT_GRAVITY_APPLIED, cascades=cascades)
            self.event_bus.emit(EVENT_ANIMATION_START, kind='fall', items=moves)
        else:
            self.event_bus.emit(EVENT_GRAVITY_APPLIED, cascades=0)
            new_tiles = self._refill()
            if new_tiles:
                self.event_bus.emit(EVENT_REFILL_COMPLETED, new_tiles=new_tiles)
                self.event_bus.emit(EVENT_ANIMATION_START, kind='refill', items=new_tiles)
        # Finally trigger board changed so cascade scan can occur
        self.event_bus.emit(EVENT_BOARD_CHANGED, reason='ability_effect', positions=positions)

    def _compute_gravity_moves(self):
        from ecs.components.board import Board
        board_comp = None
        for _, b in self.world.get_component(Board):
            board_comp = b
            break
        if board_comp is None:
            return [], 0
        moves = []
        cascades = 0
        for c in range(board_comp.cols):
            filled_rows = []
            for r in range(board_comp.rows):
                ent = self._get_entity_at(r, c)
                if ent is None:
                    continue
                tile: TileType = self.world.component_for_entity(ent, TileType)
                if tile.color is not None:
                    filled_rows.append(r)
            for target_index, original_row in enumerate(filled_rows):
                if original_row != target_index:
                    ent = self._get_entity_at(original_row, c)
                    if ent is None:
                        continue
                    tile: TileType = self.world.component_for_entity(ent, TileType)
                    moves.append({'from': (original_row, c), 'to': (target_index, c), 'color': tile.color})
            if any(m['from'][1] == c for m in moves):
                cascades += 1
        return moves, cascades

    def _apply_gravity_moves(self, moves):
        for m in moves:
            src_r, src_c = m['from']
            dst_r, dst_c = m['to']
            src_ent = self._get_entity_at(src_r, src_c)
            dst_ent = self._get_entity_at(dst_r, dst_c)
            if src_ent is None or dst_ent is None:
                continue
            src_tile: TileType = self.world.component_for_entity(src_ent, TileType)
            dst_tile: TileType = self.world.component_for_entity(dst_ent, TileType)
            dst_tile.color = src_tile.color
            src_tile.color = None

    def _refill(self):
        from ecs.systems.board import PALETTE
        spawned = []
        for ent, pos in self.world.get_component(BoardPosition):
            tile: TileType = self.world.component_for_entity(ent, TileType)
            if tile.color is None:
                import random
                tile.color = random.choice(PALETTE)
                spawned.append((pos.row, pos.col))
        return spawned

    def _get_entity_at(self, row: int, col: int):
        for ent, pos in self.world.get_component(BoardPosition):
            if pos.row == row and pos.col == col:
                return ent
        return None

    def on_mouse_press(self, sender, **payload):
        # Right-click (arcade.MOUSE_BUTTON_RIGHT == 4) cancels targeting mode.
        button = payload.get('button')
        if button != 4:  # only handle right-click
            return
        targeting = list(self.world.get_component(TargetingState))
        if not targeting:
            return
        owner_entity, targeting_state = targeting[0]
        ability_entity = targeting_state.ability_entity
        self.world.remove_component(owner_entity, TargetingState)
        self.event_bus.emit(EVENT_ABILITY_TARGET_CANCELLED, ability_entity=ability_entity, owner_entity=owner_entity, reason='right_click')
