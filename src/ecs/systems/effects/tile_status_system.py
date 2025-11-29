from __future__ import annotations

from typing import Dict, Optional, Tuple

from esper import World

from ecs.components.board_position import BoardPosition
from ecs.components.effect import Effect
from ecs.components.tile_status_overlay import TileStatusOverlay
from ecs.events.bus import (
    EVENT_EFFECT_APPLIED,
    EVENT_EFFECT_EXPIRED,
    EVENT_EFFECT_REFRESHED,
    EVENT_EFFECT_REMOVE,
    EventBus,
)


class TileStatusSystem:
    """Keeps a single overlay component per tile for lingering effects."""

    _FALLBACK_TINTS: Tuple[Tuple[int, int, int], ...] = (
        (188, 188, 188),
        (176, 208, 152),
        (152, 196, 224),
        (212, 172, 200),
    )
    _DEFAULT_TINT: Tuple[int, int, int] = (188, 188, 188)

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        event_bus.subscribe(EVENT_EFFECT_APPLIED, self.on_effect_applied)
        event_bus.subscribe(EVENT_EFFECT_REFRESHED, self.on_effect_refreshed)
        event_bus.subscribe(EVENT_EFFECT_EXPIRED, self.on_effect_expired)

    def on_effect_applied(self, sender, **payload) -> None:
        effect_entity = payload.get("effect_entity")
        owner_entity = payload.get("owner_entity")
        slug = payload.get("slug")
        if effect_entity is None or owner_entity is None or slug is None:
            return
        self._apply_overlay(effect_entity, owner_entity, slug)

    def on_effect_refreshed(self, sender, **payload) -> None:
        effect_entity = payload.get("effect_entity")
        owner_entity = payload.get("owner_entity")
        slug = payload.get("slug")
        if effect_entity is None or owner_entity is None or slug is None:
            return
        self._apply_overlay(effect_entity, owner_entity, slug)

    def on_effect_expired(self, sender, **payload) -> None:
        effect_entity = payload.get("effect_entity")
        if effect_entity is None:
            return
        tile_entity = payload.get("owner_entity")
        if tile_entity is None:
            return
        try:
            overlay = self.world.component_for_entity(tile_entity, TileStatusOverlay)
        except KeyError:
            return
        if overlay.effect_entity != effect_entity:
            return
        self.world.remove_component(tile_entity, TileStatusOverlay)

    def _apply_overlay(self, effect_entity: int, tile_entity: int, slug: str) -> None:
        if not self._is_tile_entity(tile_entity):
            return
        try:
            effect = self.world.component_for_entity(effect_entity, Effect)
        except KeyError:
            return
        icon_key = self._extract_icon(effect.metadata)
        tint = self._extract_tint(effect.metadata)
        metadata = dict(effect.metadata)

        if icon_key is None and tint is None:
            tint = self._fallback_tint(slug)
            metadata.setdefault("overlay_tint", tint)
            metadata.setdefault("overlay_marker", "fallback")

        existing: Optional[TileStatusOverlay]
        try:
            existing = self.world.component_for_entity(tile_entity, TileStatusOverlay)
        except KeyError:
            existing = None

        if existing is not None:
            if existing.effect_entity != effect_entity:
                previous_effect = existing.effect_entity
                existing.effect_entity = effect_entity
                # Remove the superseded effect entity; consumers listening for
                # EVENT_EFFECT_REMOVE will gracefully expire it.
                self.event_bus.emit(
                    EVENT_EFFECT_REMOVE,
                    effect_entity=previous_effect,
                    reason="tile_status_replaced",
                )
            existing.slug = slug
            existing.icon_key = icon_key
            existing.tint = tint
            existing.metadata.clear()
            existing.metadata.update(metadata)
            return

        overlay = TileStatusOverlay(
            slug=slug,
            effect_entity=effect_entity,
            icon_key=icon_key,
            tint=tint,
            metadata=metadata,
        )
        self.world.add_component(tile_entity, overlay)

    def _is_tile_entity(self, entity: int) -> bool:
        try:
            self.world.component_for_entity(entity, BoardPosition)
        except KeyError:
            return False
        return True

    @staticmethod
    def _extract_icon(metadata: Dict[str, object]) -> Optional[str]:
        icon_value = metadata.get("overlay_icon")
        return icon_value if isinstance(icon_value, str) else None

    @staticmethod
    def _extract_tint(metadata: Dict[str, object]) -> Optional[Tuple[int, int, int]]:
        tint_value = metadata.get("overlay_tint")
        if isinstance(tint_value, (list, tuple)):
            values = list(tint_value)[:3]
            if len(values) == 3:
                try:
                    return tuple(int(v) for v in values)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    return None
        return None

    @classmethod
    def _fallback_tint(cls, slug: str) -> Tuple[int, int, int]:
        if not cls._FALLBACK_TINTS:
            return cls._DEFAULT_TINT
        if not slug:
            return cls._DEFAULT_TINT
        total = sum(ord(ch) for ch in slug)
        index = total % len(cls._FALLBACK_TINTS)
        return cls._FALLBACK_TINTS[index]
