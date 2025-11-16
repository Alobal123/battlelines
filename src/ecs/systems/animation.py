from ecs.events.bus import (EVENT_TICK, EventBus, EVENT_ANIMATION_START, EVENT_ANIMATION_COMPLETE,
                             EVENT_TILE_SWAP_REQUEST, EVENT_TILE_SWAP_VALID, EVENT_TILE_SWAP_INVALID,
                             EVENT_TILE_SWAP_DO, EVENT_TILE_SWAP_FINALIZE)
from ecs.components.animation_swap import SwapAnimation
from ecs.components.animation_fade import FadeAnimation
from ecs.components.animation_fall import FallAnimation
from ecs.components.animation_refill import RefillAnimation
# TileType now used; color access remains via compatibility .color property when needed.
from ecs.components.duration import Duration
from ecs.factories.animation_factory import AnimationFactory
from esper import World
from typing import Tuple
from ecs.components.duration import Duration
from ecs.components.board_position import BoardPosition

class AnimationSystem:
    """Drives timing of animations; each animation is its own component instance."""
    def __init__(self, world: World, event_bus: EventBus):
        self.world = world
        self.event_bus = event_bus
        self.swap_entity: int | None = None
        self.factory = AnimationFactory(world)
        # Store validity outcomes received before swap entity exists.
        self._pending_swap_outcomes: dict[tuple[int,int], bool] = {}
        # Track finalize wait elapsed time to auto-complete in test environments lacking finalize event.
        self._finalize_wait_elapsed: float = 0.0
        event_bus.subscribe(EVENT_TICK, self.on_tick)
        event_bus.subscribe(EVENT_ANIMATION_START, self.on_animation_start)
        event_bus.subscribe(EVENT_TILE_SWAP_REQUEST, self.on_swap_request)
        event_bus.subscribe(EVENT_TILE_SWAP_VALID, self.on_swap_valid)
        event_bus.subscribe(EVENT_TILE_SWAP_INVALID, self.on_swap_invalid)
        event_bus.subscribe(EVENT_TILE_SWAP_FINALIZE, self.on_swap_finalize)

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
            # Apply any pending outcome captured earlier.
            key = (src, dst)
            swap = self._active_swap()
            if swap and key in self._pending_swap_outcomes:
                outcome = self._pending_swap_outcomes.pop(key)
                swap.valid = outcome

    def on_swap_valid(self, sender, **kwargs):
        src = kwargs.get('src'); dst = kwargs.get('dst')
        swap = self._active_swap()
        if swap and swap.src == src and swap.dst == dst:
            swap.valid = True
        else:
            # Store for later if entity not yet created.
            if src and dst:
                self._pending_swap_outcomes[(src, dst)] = True

    def on_swap_invalid(self, sender, **kwargs):
        src = kwargs.get('src'); dst = kwargs.get('dst')
        swap = self._active_swap()
        if swap and swap.src == src and swap.dst == dst:
            swap.valid = False
            if swap.progress >= 1.0 and swap.phase == 'forward':
                swap.phase = 'reverse'
        else:
            if src and dst:
                self._pending_swap_outcomes[(src, dst)] = False

    def on_swap_finalize(self, sender, **kwargs):
        src = kwargs.get('src'); dst = kwargs.get('dst')
        swap = self._active_swap()
        if swap and swap.src == src and swap.dst == dst and swap.phase == 'finalize_wait':
            self._end_swap()

    def on_animation_start(self, sender, **kwargs):
        kind = kwargs.get('kind'); items = kwargs.get('items', [])
        if kind == 'fade':
            self.factory.create_fade_group(items)
        elif kind == 'fall':
            # items contain dicts with 'from'/'to' only; color derived at render via TileTypes
            self.factory.create_fall_group(items)
        elif kind == 'refill':
            self.factory.create_refill_group(items)

    def on_tick(self, sender, **kwargs):
        dt = kwargs.get('dt', 1/60)
        # Swap progression
        swap = self._active_swap()
        if swap:
            if swap.phase == 'forward':
                dur = self.world.component_for_entity(self.swap_entity, Duration) if self.swap_entity is not None else Duration(0.2)
                swap.progress += dt / dur.value
                if swap.progress >= 1.0:
                    swap.progress = 1.0
                    # Now wait for external validity decision if not known yet.
                    if swap.valid is True:
                        self.event_bus.emit(EVENT_TILE_SWAP_DO, src=swap.src, dst=swap.dst)
                        # Enter finalize wait phase until EVENT_TILE_SWAP_FINALIZE arrives.
                        swap.phase = 'finalize_wait'
                    elif swap.valid is False:
                        swap.phase = 'reverse'
                    else:
                        # Remain at full progress until validity event sets True/False.
                        pass
            elif swap.phase == 'reverse':
                dur = self.world.component_for_entity(self.swap_entity, Duration) if self.swap_entity is not None else Duration(0.2)
                swap.progress -= dt / dur.value
                if swap.progress <= 0.0:
                    swap.progress = 0.0
                    self._end_swap()
                elif swap.progress < 0.0:
                    swap.progress = 0.0
            elif swap.phase == 'finalize_wait':
                # Auto finalize after short grace if no explicit finalize event.
                self._finalize_wait_elapsed += dt
                if self._finalize_wait_elapsed >= 0.05:  # ~3 frames at 60fps
                    self._end_swap()
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
                items = [{'from':fall.src,'to':fall.dst} for _, fall in falls]
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

    # Removed internal swap validity prediction to enforce pure event-driven validation.

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
        self._pending_swap_outcomes.clear()
        self._finalize_wait_elapsed = 0.0

    def _delete_animation_entity(self, ent: int, comp_type):
        """Robust deletion: remove animation, duration, board position then entity."""

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
