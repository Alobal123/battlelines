from ecs.events.bus import (EVENT_TICK, EventBus, EVENT_ANIMATION_START, EVENT_ANIMATION_COMPLETE,
                             EVENT_TILE_SWAP_REQUEST, EVENT_TILE_SWAP_VALID, EVENT_TILE_SWAP_INVALID,
                             EVENT_TILE_SWAP_DO, EVENT_TILE_SWAP_FINALIZE)
from ecs.components.animation_swap import SwapAnimation
from ecs.components.animation_fade import FadeAnimation
from ecs.components.animation_fall import FallAnimation
from ecs.components.animation_refill import RefillAnimation
from ecs.components.tile import TileColor
from ecs.components.board_position import BoardPosition
from ecs.components.duration import Duration
from ecs.animation_factory import AnimationFactory
from esper import World
from typing import Tuple

class AnimationSystem:
    """Drives timing of animations; each animation is its own component instance."""
    def __init__(self, world: World, event_bus: EventBus):
        self.world = world
        self.event_bus = event_bus
        self.swap_entity: int | None = None
        self.factory = AnimationFactory(world)
        event_bus.subscribe(EVENT_TICK, self.on_tick)
        event_bus.subscribe(EVENT_ANIMATION_START, self.on_animation_start)
        event_bus.subscribe(EVENT_TILE_SWAP_REQUEST, self.on_swap_request)
        event_bus.subscribe(EVENT_TILE_SWAP_VALID, self.on_swap_valid)
        event_bus.subscribe(EVENT_TILE_SWAP_INVALID, self.on_swap_invalid)

    def _active_swap(self) -> SwapAnimation | None:
        if self.swap_entity is None:
            return None
        try:
            return self.world.component_for_entity(self.swap_entity, SwapAnimation)
        except Exception:
            return None

    def on_swap_request(self, sender, **kwargs):
        src = kwargs.get('src'); dst = kwargs.get('dst')
        if not src or not dst:
            return
        if self._active_swap() is None:
            self.swap_entity = self.factory.create_swap(src, dst)

    def on_swap_valid(self, sender, **kwargs):
        src = kwargs.get('src'); dst = kwargs.get('dst')
        swap = self._active_swap()
        if swap and swap.src == src and swap.dst == dst:
            swap.valid = True

    def on_swap_invalid(self, sender, **kwargs):
        src = kwargs.get('src'); dst = kwargs.get('dst')
        swap = self._active_swap()
        if swap and swap.src == src and swap.dst == dst:
            swap.valid = False
            if swap.progress >= 1.0 and swap.phase == 'forward':
                swap.phase = 'reverse'

    def on_animation_start(self, sender, **kwargs):
        kind = kwargs.get('kind'); items = kwargs.get('items', [])
        if kind == 'fade':
            self.factory.create_fade_group(items)
        elif kind == 'fall':
            self.factory.create_fall_group(items)
        elif kind == 'refill':
            self.factory.create_refill_group(items)

    def on_tick(self, sender, **kwargs):
        dt = kwargs.get('dt', 1/60)
        # Swap progression
        swap = self._active_swap()
        if swap:
            if swap.phase == 'forward':
                # Get duration component for swap
                dur = self.world.component_for_entity(self.swap_entity, Duration) if self.swap_entity is not None else Duration(0.2)
                swap.progress += dt / dur.value
                if swap.progress >= 1.0:
                    swap.progress = 1.0
                    if swap.valid is True:
                        self.event_bus.emit(EVENT_TILE_SWAP_DO, src=swap.src, dst=swap.dst)
                        self._end_swap()
                    elif swap.valid is False:
                        swap.phase = 'reverse'
                    else:
                        pred = self._predict_swap_valid(swap.src, swap.dst)
                        swap.valid = pred
                        if pred:
                            self.event_bus.emit(EVENT_TILE_SWAP_DO, src=swap.src, dst=swap.dst)
                            self._end_swap()
                        else:
                            swap.phase = 'reverse'
            elif swap.phase == 'reverse':
                dur = self.world.component_for_entity(self.swap_entity, Duration) if self.swap_entity is not None else Duration(0.2)
                swap.progress -= dt / dur.value
                if swap.progress <= 0.0:
                    swap.progress = 0.0
                    self._end_swap()
                else:
                    if swap.progress < 0.0:
                        swap.progress = 0.0
        # Fade progression
        fades = list(self.world.get_component(FadeAnimation))
        if fades:
            for ent, fade in fades:
                if fade.alpha > 0.0:
                    d = self.world.component_for_entity(ent, Duration)
                    fade.alpha -= dt / d.value
                    if fade.alpha < 0.0:
                        fade.alpha = 0.0
            if all(fade.alpha <= 0.0 for _, fade in fades):
                positions = [fade.pos for _, fade in fades]
                for ent, _ in fades:
                    self._delete_animation_entity(ent, FadeAnimation)
                self.event_bus.emit(EVENT_ANIMATION_COMPLETE, kind='fade', items=positions)
        # Fall progression
        falls = list(self.world.get_component(FallAnimation))
        if falls:
            for ent, fall in falls:
                if fall.linear < 1.0:
                    d = self.world.component_for_entity(ent, Duration)
                    fall.linear += dt / d.value
                    if fall.linear > 1.0:
                        fall.linear = 1.0
            if all(fall.linear >= 1.0 for _, fall in falls):
                items = [{'from':fall.src,'to':fall.dst,'color':fall.color} for _, fall in falls]
                for ent, _ in falls:
                    self._delete_animation_entity(ent, FallAnimation)
                self.event_bus.emit(EVENT_ANIMATION_COMPLETE, kind='fall', items=items)
        # Refill progression
        refills = list(self.world.get_component(RefillAnimation))
        if refills:
            for ent, refill in refills:
                if refill.linear < 1.0:
                    d = self.world.component_for_entity(ent, Duration)
                    refill.linear += dt / d.value
                    if refill.linear > 1.0:
                        refill.linear = 1.0
            if all(refill.linear >= 1.0 for _, refill in refills):
                positions = [refill.pos for _, refill in refills]
                for ent, _ in refills:
                    self._delete_animation_entity(ent, RefillAnimation)
                self.event_bus.emit(EVENT_ANIMATION_COMPLETE, kind='refill', items=positions)

    def _get_entity_at(self, row: int, col: int):
        for ent, pos in self.world.get_component(BoardPosition):
            if pos.row == row and pos.col == col:
                return ent
        return None

    def _predict_swap_valid(self, a, b) -> bool:
        # Mirror logic from MatchSystem.creates_match
        grid = {}
        for ent, pos in self.world.get_component(BoardPosition):
            color_comp = self.world.component_for_entity(ent, TileColor)
            grid[(pos.row, pos.col)] = color_comp.color
        if a not in grid or b not in grid:
            return False
        grid[a], grid[b] = grid[b], grid[a]
        def has_line(pos):
            row, col = pos
            color = grid.get(pos)
            if color is None:
                return False
            # Horizontal
            h = [(row,col)]
            c = col-1
            while (row,c) in grid and grid[(row,c)] == color:
                h.append((row,c)); c -= 1
            c = col+1
            while (row,c) in grid and grid[(row,c)] == color:
                h.append((row,c)); c += 1
            if len(h) >= 3:
                return True
            # Vertical
            v = [(row,col)]
            r = row-1
            while (r,col) in grid and grid[(r,col)] == color:
                v.append((r,col)); r -= 1
            r = row+1
            while (r,col) in grid and grid[(r,col)] == color:
                v.append((r,col)); r += 1
            return len(v) >= 3
        return has_line(a) or has_line(b)

    def _remove_component(self, comp_type):
        # Delete all entities that carry this component. Use defensive removal in case delete_entity doesn't purge immediately.
        ents = [ent for ent, _ in self.world.get_component(comp_type)]
        for ent in ents:
            try:
                self.world.delete_entity(ent)
            except Exception:
                # Fallback: remove component only
                try:
                    self.world.remove_component(ent, comp_type)
                except Exception:
                    pass

    def _end_swap(self):
        if self.swap_entity is not None:
            self._delete_animation_entity(self.swap_entity, SwapAnimation)
        self.swap_entity = None

    def _delete_animation_entity(self, ent: int, comp_type):
        """Robust deletion: remove animation, duration, board position then entity."""
        from ecs.components.duration import Duration
        from ecs.components.board_position import BoardPosition
        # Remove specific animation component
        try:
            self.world.remove_component(ent, comp_type)
        except Exception:
            pass
        # Remove auxiliary components
        for aux in (Duration, BoardPosition):
            try:
                self.world.remove_component(ent, aux)
            except Exception:
                pass
        # Finally delete entity
        try:
            self.world.delete_entity(ent)
        except Exception:
            pass
