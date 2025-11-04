from ecs.events.bus import (EVENT_TICK, EventBus, EVENT_TILE_SELECTED, EVENT_TILE_SWAP_REQUEST,
                            EVENT_TILE_SWAP_FINALIZE, EVENT_TILE_SWAP_DO, EVENT_TILE_SWAP_VALID, EVENT_TILE_SWAP_INVALID,
                            EVENT_GRAVITY_MOVES, EVENT_GRAVITY_SETTLED, EVENT_REFILL_COMPLETED, EVENT_MATCH_FOUND, EVENT_MATCH_CLEARED,
                            EVENT_MATCH_CLEAR_BEGIN, EVENT_MATCH_FADE_COMPLETE)
from ecs.components.tile import BoardCell, TileColor
from ecs.constants import GRID_ROWS, GRID_COLS, TILE_SIZE, BOTTOM_MARGIN
from esper import World
import arcade

PADDING = 4

class RenderSystem:
    def __init__(self, world: World, event_bus: EventBus, window):
        self.world = world
        self.event_bus = event_bus
        self.window = window
        self.event_bus.subscribe(EVENT_TICK, self.on_tick)
        self.event_bus.subscribe(EVENT_TILE_SELECTED, self.on_tile_selected)
        self.event_bus.subscribe(EVENT_TILE_SWAP_REQUEST, self.on_swap_request)
        self.event_bus.subscribe(EVENT_TILE_SWAP_VALID, self.on_swap_valid)
        self.event_bus.subscribe(EVENT_TILE_SWAP_INVALID, self.on_swap_invalid)
        self.event_bus.subscribe(EVENT_TILE_SWAP_FINALIZE, self.on_swap_finalize)
        self.event_bus.subscribe(EVENT_GRAVITY_MOVES, self.on_gravity_moves)
        self.event_bus.subscribe(EVENT_GRAVITY_SETTLED, self.on_gravity_settled)
        self.event_bus.subscribe(EVENT_REFILL_COMPLETED, self.on_refill_completed)
        self.event_bus.subscribe(EVENT_MATCH_FOUND, self.on_match_found)
        self.event_bus.subscribe(EVENT_MATCH_CLEARED, self.on_match_cleared)
        self.event_bus.subscribe(EVENT_MATCH_CLEAR_BEGIN, self.on_match_clear_begin)
        self.selected = None
        self.active_swap = None  # (src, dst, progress 0..1)
        self.swap_duration = 0.2  # seconds
        self.accumulated_time = 0.0
        self.swap_phase = None  # 'forward' or 'reverse'
        self.pending_swap_valid = None  # True/False when a swap starts
        self.falling = []  # list of dict {from:(r,c), to:(r,c), color, linear 0..1}
        self.fall_duration = 0.25
        self.refill_spawn = []  # new tiles appearing from above with linear progress
        self.refill_duration = 0.25
        self.use_easing = True  # toggle for quadratic ease-in-out
        self.fading = []  # list of {'pos':(r,c), 'color':(r,g,b), 'alpha':1.0}
        self.fade_duration = 0.2

    def on_tick(self, sender, **kwargs):
        dt = kwargs.get('dt', 1/60)
        # Swap animation
        if self.active_swap:
            (src, dst, progress) = self.active_swap
            if self.swap_phase == 'forward':
                progress += dt / self.swap_duration
                if progress >= 1.0:
                    progress = 1.0
                    # If validity not yet known, hold at end frame until decision arrives
                    if self.pending_swap_valid is None:
                        self.active_swap = (src, dst, progress)
                        return
                    if self.pending_swap_valid:
                        self.event_bus.emit(EVENT_TILE_SWAP_DO, src=src, dst=dst)
                        self.active_swap = None
                        self.swap_phase = None
                        self.pending_swap_valid = None
                        self.selected = None  # deselect after successful swap
                        return
                    else:
                        self.swap_phase = 'reverse'
                self.active_swap = (src, dst, progress)
            elif self.swap_phase == 'reverse':
                progress -= dt / self.swap_duration
                if progress <= 0.0:
                    progress = 0.0
                    self.active_swap = None
                    self.swap_phase = None
                    self.pending_swap_valid = None
                    self.selected = None  # deselect after invalid swap reversal
                else:
                    self.active_swap = (src, dst, progress)
        # Falling animations
        if self.falling:
            finished = []
            for f in self.falling:
                linear = f['linear'] + dt / self.fall_duration
                f['linear'] = min(1.0, linear)
                if linear >= 1.0:
                    finished.append(f)
            for f in finished:
                self.falling.remove(f)
            if finished and not self.falling:
                self.event_bus.emit(EVENT_GRAVITY_SETTLED, moves=finished)
        # Refill animations (progress independent of fade)
        if self.refill_spawn:
            done = []
            for r in self.refill_spawn:
                linear = r['linear'] + dt / self.refill_duration
                r['linear'] = min(1.0, linear)
                if linear >= 1.0:
                    done.append(r)
            for r in done:
                self.refill_spawn.remove(r)
            if done and not self.refill_spawn:
                from ecs.events.bus import EVENT_REFILL_ANIM_DONE
                self.event_bus.emit(EVENT_REFILL_ANIM_DONE)
        # Fade-out animations
        if self.fading:
            finished = []
            for f in self.fading:
                f['alpha'] -= dt / self.fade_duration
                if f['alpha'] <= 0.0:
                    f['alpha'] = 0.0
                    finished.append(f)
            for f in finished:
                self.fading.remove(f)
            if not self.fading and finished:
                # Fade cycle finished
                self.event_bus.emit(EVENT_MATCH_FADE_COMPLETE, positions=[f['pos'] for f in finished])
            # (Refill progress already processed above)

    def on_tile_selected(self, sender, **kwargs):
        self.selected = (kwargs.get('row'), kwargs.get('col'))

    def on_swap_request(self, sender, **kwargs):
        # Start optimistic forward animation immediately; validity decides outcome when forward animation completes.
        src = kwargs.get('src')
        dst = kwargs.get('dst')
        if src and dst and not self.active_swap:
            self.active_swap = (src, dst, 0.0)
            self.swap_phase = 'forward'
            self.pending_swap_valid = None  # will be set True/False on valid/invalid event
            self.selected = None  # deselect immediately when initiating any swap attempt

    def on_swap_valid(self, sender, **kwargs):
        src = kwargs.get('src')
        dst = kwargs.get('dst')
        if src and dst:
            if self.active_swap and self.active_swap[0] == src and self.active_swap[1] == dst:
                # Animation already begun on request; just flag validity
                self.pending_swap_valid = True
            elif not self.active_swap:
                # Fallback: start animation if not already started
                self.active_swap = (src, dst, 0.0)
                self.swap_phase = 'forward'
                self.pending_swap_valid = True

    def on_swap_invalid(self, sender, **kwargs):
        src = kwargs.get('src')
        dst = kwargs.get('dst')
        if src and dst:
            if self.active_swap and self.active_swap[0] == src and self.active_swap[1] == dst:
                self.pending_swap_valid = False
            elif not self.active_swap:
                self.active_swap = (src, dst, 0.0)
                self.swap_phase = 'forward'
                self.pending_swap_valid = False

    def on_swap_finalize(self, sender, **kwargs):
        # Rendering system does not perform swap; BoardSystem emits finalize after data swap
        pass

    def process(self):
        # Background already cleared in window.on_draw
        # Compute grid origin (bottom-center) using left/bottom corner
        total_width = GRID_COLS * TILE_SIZE
        start_x = (self.window.width - total_width) / 2
        start_y = BOTTOM_MARGIN
        # Precompute positions for animation interpolation
        positions = {}
        for ent, cell in self.world.get_component(BoardCell):
            cx = start_x + cell.col * TILE_SIZE + TILE_SIZE/2
            cy = start_y + cell.row * TILE_SIZE + TILE_SIZE/2
            positions[(cell.row, cell.col)] = (ent, cx, cy)

        # Draw tiles (with animation if active swap)
        for (row, col), (ent, base_x, base_y) in positions.items():
            color_comp = self.world.component_for_entity(ent, TileColor)
            color = color_comp.color
            alpha_override = None
            # If cleared, maybe we have fading copy to draw instead of skip
            if color is None:
                # search fading list
                for f in self.fading:
                    if f['pos'] == (row, col):
                        color = f['color']
                        alpha_override = f['alpha']
                        break
                if color is None:
                    continue
            draw_x, draw_y = base_x, base_y
            # Swap animation interpolation
            if self.active_swap:
                (src, dst, progress) = self.active_swap
                if (row, col) == src or (row, col) == dst:
                    src_pos = positions[src][1:]
                    dst_pos = positions[dst][1:]
                    if (row, col) == src:
                        draw_x = src_pos[0] + (dst_pos[0] - src_pos[0]) * progress
                        draw_y = src_pos[1] + (dst_pos[1] - src_pos[1]) * progress
                    else:
                        draw_x = dst_pos[0] + (src_pos[0] - dst_pos[0]) * progress
                        draw_y = dst_pos[1] + (src_pos[1] - dst_pos[1]) * progress
            # Falling interpolation
            for f in self.falling:
                if f['to'] == (row, col):
                    from_pos = positions[f['from']][1:]
                    to_pos = positions[f['to']][1:]
                    p_lin = f['linear']
                    p = p_lin
                    if self.use_easing:
                        if p < 0.5:
                            p = 2 * p * p
                        else:
                            p = -2 * p * p + 4 * p -1
                    draw_x = from_pos[0] + (to_pos[0] - from_pos[0]) * p
                    draw_y = from_pos[1] + (to_pos[1] - from_pos[1]) * p
            # Refill spawn (appear from above)
            for r in self.refill_spawn:
                if r['pos'] == (row, col):
                    to_pos = positions[(row, col)][1:]
                    start_y2 = to_pos[1] + TILE_SIZE * 1.2
                    p_lin = r['linear']
                    p = p_lin
                    if self.use_easing:
                        if p < 0.5:
                            p = 2 * p * p
                        else:
                            p = -2 * p * p + 4 * p -1
                    draw_y = start_y2 + (to_pos[1] - start_y2) * p
            radius = (TILE_SIZE - PADDING) / 2
            if alpha_override is not None and hasattr(arcade, 'draw_circle_filled'):  # alpha blend
                arcade.draw_circle_filled(draw_x, draw_y, radius, (*color, int(255*alpha_override)))
            else:
                arcade.draw_circle_filled(draw_x, draw_y, radius, color)
            if self.selected and (row, col) == self.selected:
                arcade.draw_circle_outline(draw_x, draw_y, radius, (255,255,255), 3)
    def on_match_found(self, sender, **kwargs):
        # Pure notification; setup occurs on CLEAR_BEGIN
        pass

    def on_match_clear_begin(self, sender, **kwargs):
        positions = kwargs.get('positions', [])
        self.fading = []
        for (r,c) in positions:
            ent = self._get_entity_at(r,c)
            if ent is None:
                continue
            color_comp: TileColor = self.world.component_for_entity(ent, TileColor)
            self.fading.append({'pos':(r,c), 'color':color_comp.color, 'alpha':1.0})

    def on_match_cleared(self, sender, **kwargs):
        # Nothing extra; fading list already set
        pass

    def on_gravity_moves(self, sender, **kwargs):
        moves = kwargs.get('moves', [])
        # Initialize falling entries
        self.falling = [{**m, 'linear': 0.0} for m in moves]

    def on_gravity_settled(self, sender, **kwargs):
        # Gravity visual finished; logical refill handled by MatchResolutionSystem after this event.
        pass
    def _get_entity_at(self, row: int, col: int):
        for ent, cell in self.world.get_component(BoardCell):
            if cell.row == row and cell.col == col:
                return ent
        return None

    def on_refill_completed(self, sender, **kwargs):
        new_tiles = kwargs.get('new_tiles', [])
        self.refill_spawn = [{'pos': pos, 'linear': 0.0} for pos in new_tiles]

