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
    EVENT_CASCADE_STEP,
    EVENT_CASCADE_COMPLETE,
    EVENT_EFFECT_APPLY,
    EVENT_REGIMENT_CLICK,
)
from ecs.components.ability import Ability
from ecs.components.targeting_state import TargetingState
from ecs.components.board_position import BoardPosition
from ecs.components.active_switch import ActiveSwitch
from ecs.components.tile_type_registry import TileTypeRegistry
from ecs.components.tile_types import TileTypes
from ecs.components.tile import TileType
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.ability_target import AbilityTarget


class AbilitySystem:
    """Ability activation, targeting, and effect application.

        Abilities:
            tactical_shift: Convert all tiles of the selected tile's color to the configured target type (default ranged).
      crimson_pulse: Clear (remove) a 3x3 area centered on the selected tile (set color=None).
    """

    def __init__(self, world: World, event_bus: EventBus):
        self.world = world
        self.event_bus = event_bus
        self._cascade_active = False
        self._cascade_step_observed = False
        self._ability_owner_cache = {}
        event_bus.subscribe(EVENT_ABILITY_ACTIVATE_REQUEST, self.on_activate_request)
        # Spend now delayed; we no longer subscribe to immediate spent for targeting.
        event_bus.subscribe(EVENT_TILE_BANK_INSUFFICIENT, self.on_bank_insufficient)
        event_bus.subscribe(EVENT_TILE_CLICK, self.on_tile_click)
        event_bus.subscribe(EVENT_TILE_BANK_SPENT, self.on_bank_spent)
        event_bus.subscribe(EVENT_MOUSE_PRESS, self.on_mouse_press)
        event_bus.subscribe(EVENT_CASCADE_STEP, self.on_cascade_step)
        event_bus.subscribe(EVENT_CASCADE_COMPLETE, self.on_cascade_complete)
        event_bus.subscribe(EVENT_REGIMENT_CLICK, self.on_regiment_click)

    def on_activate_request(self, sender, **payload):
        # Block ability activation while cascade active
        if self._cascade_active:
            return
        ability_entity = payload['ability_entity']
        owner_entity = payload['owner_entity']
        # Validate that owner_entity actually owns this ability and is current active turn
        from ecs.components.ability_list_owner import AbilityListOwner
        from ecs.components.active_turn import ActiveTurn
        owners = {ent: comp for ent, comp in self.world.get_component(AbilityListOwner)}
        if owner_entity not in owners:
            return
        if ability_entity not in owners[owner_entity].ability_entities:
            # Ability doesn't belong to provided owner; reject activation
            return
        self._ability_owner_cache[ability_entity] = owner_entity
        active_list = list(self.world.get_component(ActiveTurn))
        if active_list and active_list[0][1].owner_entity != owner_entity:
            # Not this owner's turn
            return
        # Enter targeting mode first; cost will be spent only after effect applied.
        self.world.add_component(owner_entity, TargetingState(ability_entity=ability_entity))
        self.event_bus.emit(EVENT_ABILITY_TARGET_MODE, ability_entity=ability_entity, owner_entity=owner_entity)

    def on_bank_insufficient(self, sender, **payload):
        return

    def on_tile_click(self, sender, **payload):
        targeting = list(self.world.get_component(TargetingState))
        if not targeting:
            return
        if self._cascade_active:
            return
        owner_entity, targeting_state = targeting[0]
        ability_entity = targeting_state.ability_entity
        if not isinstance(ability_entity, int):
            return
        try:
            ability_target = self.world.component_for_entity(ability_entity, AbilityTarget)
        except KeyError:
            return
        if ability_target.target_type != 'tile':
            return
        row = payload['row']
        col = payload['col']
        ability = self.world.component_for_entity(ability_entity, Ability)
        self.world.add_component(
            ability_entity,
            PendingAbilityTarget(
                ability_entity=ability_entity,
                owner_entity=owner_entity,
                row=row,
                col=col,
            ),
        )
        self.event_bus.emit(
            EVENT_TILE_BANK_SPEND_REQUEST,
            entity=owner_entity,
            cost=ability.cost,
            ability_entity=ability_entity,
        )
        self.world.remove_component(owner_entity, TargetingState)
        self.event_bus.emit(
            EVENT_ABILITY_TARGET_SELECTED,
            ability_entity=ability_entity,
            target=(row, col),
        )

    def on_regiment_click(self, sender, **payload):
        targeting = list(self.world.get_component(TargetingState))
        if not targeting:
            return
        if self._cascade_active:
            return
        owner_entity, targeting_state = targeting[0]
        ability_entity = targeting_state.ability_entity
        if not isinstance(ability_entity, int):
            return
        try:
            ability_target = self.world.component_for_entity(ability_entity, AbilityTarget)
        except KeyError:
            return
        if ability_target.target_type != 'regiment':
            return
        regiment_entity = payload.get('regiment_entity')
        if regiment_entity is None:
            return
        clicked_owner = payload.get('owner_entity')
        if clicked_owner is not None and clicked_owner != owner_entity:
            return
        ability = self.world.component_for_entity(ability_entity, Ability)
        self.world.add_component(
            ability_entity,
            PendingAbilityTarget(
                ability_entity=ability_entity,
                owner_entity=owner_entity,
                target_entity=regiment_entity,
            ),
        )
        self.event_bus.emit(
            EVENT_TILE_BANK_SPEND_REQUEST,
            entity=owner_entity,
            cost=ability.cost,
            ability_entity=ability_entity,
        )
        self.world.remove_component(owner_entity, TargetingState)
        self.event_bus.emit(
            EVENT_ABILITY_TARGET_SELECTED,
            ability_entity=ability_entity,
            target=regiment_entity,
        )

    def on_bank_spent(self, sender, **payload):
        # Reset cascade step observation for this ability resolution
        self._cascade_step_observed = False
        ability_entity = payload.get('ability_entity')
        if ability_entity is None:
            return
        # Retrieve pending target component
        try:
            pending: PendingAbilityTarget = self.world.component_for_entity(ability_entity, PendingAbilityTarget)
        except KeyError:
            return  # No pending target stored
        owner_entity = self._resolve_owner_for_ability(ability_entity, default=pending.owner_entity)
        row = pending.row
        col = pending.col
        ability = self.world.component_for_entity(ability_entity, Ability)
        if ability.name == 'tactical_shift':
            if row is None or col is None:
                self.world.remove_component(ability_entity, PendingAbilityTarget)
                self._ability_owner_cache.pop(ability_entity, None)
                return
            affected = self._apply_transform_all_color_to_target(row, col, ability)
            self.event_bus.emit(EVENT_ABILITY_EFFECT_APPLIED, ability_entity=ability_entity, affected=affected)
            # Emit match-like cleared event for resource attribution
            active_owner = self._get_active_owner()
            self.event_bus.emit(EVENT_BOARD_CHANGED, reason='ability_effect', positions=affected)
            registry = self._registry()
            types_payload = []   # (r,c,type_name) for logic
            for (r, c) in affected:
                ent = self._get_entity_at(r, c)
                if ent is None:
                    continue
                sw: ActiveSwitch = self.world.component_for_entity(ent, ActiveSwitch)
                if not sw.active:
                    continue
                tt: TileType = self.world.component_for_entity(ent, TileType)
                types_payload.append((r, c, tt.type_name))
            self.event_bus.emit(EVENT_MATCH_CLEARED, positions=affected, types=types_payload, owner_entity=active_owner)
            # If no cascade step emitted (no matches created), emit cascade_complete(depth=0) to finalize turn rotation
            if not self._cascade_step_observed:
                self.event_bus.emit(EVENT_CASCADE_COMPLETE, depth=0)
        elif ability.name == 'crimson_pulse':
            if row is None or col is None:
                self.world.remove_component(ability_entity, PendingAbilityTarget)
                self._ability_owner_cache.pop(ability_entity, None)
                return
            positions = self._prepare_crimson_pulse_area(row, col)
            active_owner = self._get_active_owner()
            # Resolve clear and subsequent gravity/refill; emits board_changed after completion
            _, types_payload = self._resolve_external_clear(positions)
            self.event_bus.emit(EVENT_ABILITY_EFFECT_APPLIED, ability_entity=ability_entity, affected=positions)
            # Single attributed match cleared event (after logical clear, before cascade scan)
            self.event_bus.emit(EVENT_MATCH_CLEARED, positions=positions, types=types_payload, owner_entity=active_owner)
            if not self._cascade_step_observed:
                self.event_bus.emit(EVENT_CASCADE_COMPLETE, depth=0)
        else:
            if ability.name == 'bolster_morale':
                target_entity = pending.target_entity
                if target_entity is not None:
                    bonus = ability.params.get('morale_bonus', 20)
                    turns = ability.params.get('turns', 3)
                    self.event_bus.emit(
                        EVENT_EFFECT_APPLY,
                        owner_entity=target_entity,
                        source_entity=ability_entity,
                        slug='morale_boost',
                        stacks=True,
                        metadata={
                            'morale_bonus': bonus,
                            'turns': turns,
                            'caster_owner': owner_entity,
                        },
                        turns=turns,
                    )
                    self.event_bus.emit(
                        EVENT_ABILITY_EFFECT_APPLIED,
                        ability_entity=ability_entity,
                        affected=[target_entity],
                    )
                    if not self._cascade_step_observed:
                        self.event_bus.emit(EVENT_CASCADE_COMPLETE, depth=0)
                else:
                    self.event_bus.emit(EVENT_ABILITY_EFFECT_APPLIED, ability_entity=ability_entity, affected=[])
                    if not self._cascade_step_observed:
                        self.event_bus.emit(EVENT_CASCADE_COMPLETE, depth=0)
            else:
                self.event_bus.emit(EVENT_ABILITY_EFFECT_APPLIED, ability_entity=ability_entity, affected=[])
        # Remove pending component after applying effect
        self.world.remove_component(ability_entity, PendingAbilityTarget)
        self._ability_owner_cache.pop(ability_entity, None)

    def _resolve_owner_for_ability(self, ability_entity: int, *, default: int | None = None) -> int | None:
        cached = self._ability_owner_cache.get(ability_entity)
        if cached is not None:
            return cached
        from ecs.components.ability_list_owner import AbilityListOwner
        for owner_ent, owner_comp in self.world.get_component(AbilityListOwner):
            if ability_entity in owner_comp.ability_entities:
                self._ability_owner_cache[ability_entity] = owner_ent
                return owner_ent
        return default

    def _apply_transform_all_color_to_target(self, row: int, col: int, ability: Ability):
        """Transform all tiles matching the clicked tile's type to the configured target type.

        ability.params['target_color'] holds the desired replacement tile type name; defaults to 'ranged'.
        Color constants are no longer used; transformation is purely semantic on type_name.
        """
        target_type = ability.params.get('target_color', 'ranged') if hasattr(ability, 'params') else 'ranged'
        registry = self._registry()
        if target_type not in registry.types:
            target_type = 'ranged'
        # Determine source type from clicked tile
        source_type = None
        for ent, pos in self.world.get_component(BoardPosition):
            if pos.row == row and pos.col == col:
                sw: ActiveSwitch = self.world.component_for_entity(ent, ActiveSwitch)
                if sw.active:
                    tt: TileType = self.world.component_for_entity(ent, TileType)
                    source_type = tt.type_name
                break
        if source_type is None:
            return []
        affected = []
        for ent, pos in self.world.get_component(BoardPosition):
            sw: ActiveSwitch = self.world.component_for_entity(ent, ActiveSwitch)
            if not sw.active:
                continue
            tt: TileType = self.world.component_for_entity(ent, TileType)
            if tt.type_name == source_type:
                tt.type_name = target_type
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
        """Clear given positions, apply gravity/refill, emit animations, then board_changed.

    Returns (colors_list, types_list) where colors_list = [(r,c,color)] for rendering attribution,
    types_list = [(r,c,type_name)] for logic attribution. Does NOT emit match_cleared itself.
        """
        if not positions:
            self.event_bus.emit(EVENT_BOARD_CHANGED, reason='ability_effect', positions=positions)
            return [], []
        colored = []
        typed = []
        for (r, c) in positions:
            ent = self._get_entity_at(r, c)
            if ent is None:
                continue
            sw: ActiveSwitch = self.world.component_for_entity(ent, ActiveSwitch)
            if sw.active:
                tt: TileType = self.world.component_for_entity(ent, TileType)
                colored.append((r, c, self._registry().background_for(tt.type_name)))
                typed.append((r, c, tt.type_name))
        # Clear tiles
        for (r, c) in positions:
            ent = self._get_entity_at(r, c)
            if ent is None:
                continue
            sw: ActiveSwitch = self.world.component_for_entity(ent, ActiveSwitch)
            sw.active = False
        # Gravity / refill
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
        # Board changed triggers cascade scan by MatchResolutionSystem
        self.event_bus.emit(EVENT_BOARD_CHANGED, reason='ability_effect', positions=positions)
        return colored, typed

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
        registry = self._registry()
        for c in range(board_comp.cols):
            filled_rows = []
            for r in range(board_comp.rows):
                ent = self._get_entity_at(r, c)
                if ent is None:
                    continue
                tile_sw: ActiveSwitch = self.world.component_for_entity(ent, ActiveSwitch)
                if tile_sw.active:
                    filled_rows.append(r)
            for target_index, original_row in enumerate(filled_rows):
                if original_row != target_index:
                    ent = self._get_entity_at(original_row, c)
                    if ent is None:
                        continue
                    tile_sw: ActiveSwitch = self.world.component_for_entity(ent, ActiveSwitch)
                    if not tile_sw.active:
                        continue
                    tile_tt: TileType = self.world.component_for_entity(ent, TileType)
                    moves.append({'from': (original_row, c), 'to': (target_index, c), 'type_name': tile_tt.type_name})
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
            src_tile_sw: ActiveSwitch = self.world.component_for_entity(src_ent, ActiveSwitch)
            dst_tile_sw: ActiveSwitch = self.world.component_for_entity(dst_ent, ActiveSwitch)
            if not src_tile_sw.active:
                continue
            src_tt: TileType = self.world.component_for_entity(src_ent, TileType)
            dst_tt: TileType = self.world.component_for_entity(dst_ent, TileType)
            dst_tt.type_name = src_tt.type_name
            dst_tile_sw.active = True
            src_tile_sw.active = False

    def _refill(self):
        spawned = []
        for ent, pos in self.world.get_component(BoardPosition):
            import random
            tile_sw: ActiveSwitch = self.world.component_for_entity(ent, ActiveSwitch)
            if not tile_sw.active:
                tt: TileType = self.world.component_for_entity(ent, TileType)
                new_type = random.choice(self._registry().all_types())
                tt.type_name = new_type
                tile_sw.active = True
                spawned.append((pos.row, pos.col))
        return spawned

    def _get_entity_at(self, row: int, col: int):
        for ent, pos in self.world.get_component(BoardPosition):
            if pos.row == row and pos.col == col:
                return ent
        return None

    def _get_active_owner(self) -> int | None:
        from ecs.components.active_turn import ActiveTurn
        active = list(self.world.get_component(ActiveTurn))
        if not active:
            return None
        return active[0][1].owner_entity

    def _registry(self) -> TileTypes:
        for ent, _ in self.world.get_component(TileTypeRegistry):
            return self.world.component_for_entity(ent, TileTypes)
        raise RuntimeError('TileTypes definitions not found')

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

    def on_cascade_step(self, sender, **payload):
        self._cascade_active = True
        self._cascade_step_observed = True

    def on_cascade_complete(self, sender, **payload):
        self._cascade_active = False
