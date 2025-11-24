from __future__ import annotations

from types import SimpleNamespace

from esper import World

from ecs.components.board_position import BoardPosition
from ecs.components.effect import Effect
from ecs.components.tile_status_overlay import TileStatusOverlay
from ecs.events.bus import EVENT_EFFECT_APPLIED, EventBus
from ecs.systems.effects.tile_status_system import TileStatusSystem
from ecs.systems.tooltip_system import TooltipSystem
from ecs.effects.factory import ensure_default_effects_registered


def _apply_effect(bus: EventBus, effect_entity: int, tile_entity: int, slug: str) -> None:
    bus.emit(
        EVENT_EFFECT_APPLIED,
        effect_entity=effect_entity,
        owner_entity=tile_entity,
        slug=slug,
    )


def test_overlay_uses_fallback_tint_when_no_icon() -> None:
    bus = EventBus()
    world = World()
    TileStatusSystem(world, bus)

    tile_entity = world.create_entity(BoardPosition(row=0, col=0))
    effect_entity = world.create_entity(
        Effect(slug="tile_sacrifice", owner_entity=tile_entity, metadata={})
    )

    _apply_effect(bus, effect_entity, tile_entity, "tile_sacrifice")

    overlay = world.component_for_entity(tile_entity, TileStatusOverlay)
    expected_tint = TileStatusSystem._fallback_tint("tile_sacrifice")
    assert overlay.icon_key is None
    assert overlay.tint == expected_tint
    assert overlay.metadata.get("overlay_tint") == expected_tint
    assert overlay.metadata.get("overlay_marker") == "fallback"


def test_overlay_respects_explicit_icon_and_tint() -> None:
    bus = EventBus()
    world = World()
    TileStatusSystem(world, bus)

    tile_entity = world.create_entity(BoardPosition(row=0, col=0))
    explicit_tint = (224, 196, 64)
    effect_entity = world.create_entity(
        Effect(
            slug="tile_guarded",
            owner_entity=tile_entity,
            metadata={
                "overlay_icon": "tile_guarded",
                "overlay_tint": explicit_tint,
            },
        )
    )

    _apply_effect(bus, effect_entity, tile_entity, "tile_guarded")

    overlay = world.component_for_entity(tile_entity, TileStatusOverlay)
    assert overlay.icon_key == "tile_guarded"
    assert overlay.tint == explicit_tint
    assert overlay.metadata.get("overlay_tint") == explicit_tint
    assert overlay.metadata.get("overlay_marker") != "fallback"


def test_tile_overlay_tooltip_describes_effect() -> None:
    ensure_default_effects_registered()
    bus = EventBus()
    world = World()
    TileStatusSystem(world, bus)

    tile_entity = world.create_entity(BoardPosition(row=0, col=0))
    effect_entity = world.create_entity(
        Effect(slug="tile_guarded", owner_entity=tile_entity, metadata={"damage": 2})
    )
    world.add_component(
        tile_entity,
        TileStatusOverlay(
            slug="tile_guarded",
            effect_entity=effect_entity,
            tint=(224, 196, 64),
            metadata={"damage": 2},
        ),
    )

    tooltip = TooltipSystem(world, bus, SimpleNamespace(width=800, height=600), render_system=None, delay=0.0)
    text = tooltip._tile_overlay_text(tile_entity)

    assert "Guarded Tile" in text
    assert "Deals damage" in text
    assert "2 damage" in text


def test_tile_overlay_tooltip_handles_missing_effect_entity() -> None:
    ensure_default_effects_registered()
    bus = EventBus()
    world = World()
    TileStatusSystem(world, bus)

    tile_entity = world.create_entity(BoardPosition(row=0, col=0))
    world.add_component(
        tile_entity,
        TileStatusOverlay(
            slug="mystic_shroud",
            effect_entity=-1,
            tint=(150, 150, 210),
            metadata={"description": "A lingering veil that does something mysterious."},
        ),
    )

    tooltip = TooltipSystem(world, bus, SimpleNamespace(width=800, height=600), render_system=None, delay=0.0)
    text = tooltip._tile_overlay_text(tile_entity)

    assert "Mystic Shroud" in text
    assert "lingering veil" in text.lower()
