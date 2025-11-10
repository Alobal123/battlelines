from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

from esper import World

from ecs.components.animation_fade import FadeAnimation
from ecs.components.animation_fall import FallAnimation
from ecs.components.animation_refill import RefillAnimation
from ecs.components.animation_swap import SwapAnimation
from ecs.components.board_position import BoardPosition

BoardPos = Tuple[int, int]


@dataclass(slots=True)
class RenderContext:
    """Frame-scoped rendering data shared across renderer subcomponents."""

    world: World
    window_width: int
    window_height: int
    tile_size: int
    board_left: float
    board_bottom: float
    board_width: float
    board_height: float
    board_positions: Dict[BoardPos, Tuple[int, float, float]]
    swap_by_pos: Dict[BoardPos, SwapAnimation] = field(default_factory=dict)
    fall_by_dst: Dict[BoardPos, FallAnimation] = field(default_factory=dict)
    refill_by_pos: Dict[BoardPos, RefillAnimation] = field(default_factory=dict)
    fade_by_pos: Dict[BoardPos, FadeAnimation] = field(default_factory=dict)

    @property
    def board_top(self) -> float:
        return self.board_bottom + self.board_height

    @property
    def board_right(self) -> float:
        return self.board_left + self.board_width


def build_render_context(
    world: World,
    window_width: int,
    window_height: int,
    rows: int,
    cols: int,
    tile_size: int,
    board_left: float,
    board_bottom: float,
    *,
    swap_by_pos: Dict[BoardPos, SwapAnimation] | None = None,
    fall_by_dst: Dict[BoardPos, FallAnimation] | None = None,
    refill_by_pos: Dict[BoardPos, RefillAnimation] | None = None,
    fade_by_pos: Dict[BoardPos, FadeAnimation] | None = None,
) -> RenderContext:
    """Populate a RenderContext for the current frame."""

    board_width = tile_size * cols
    board_height = tile_size * rows

    positions: Dict[BoardPos, Tuple[int, float, float]] = {}
    for entity, pos in world.get_component(BoardPosition):
        cx = board_left + pos.col * tile_size + tile_size / 2
        cy = board_bottom + pos.row * tile_size + tile_size / 2
        positions[(pos.row, pos.col)] = (entity, cx, cy)

    if swap_by_pos is None or fall_by_dst is None or refill_by_pos is None or fade_by_pos is None:
        swap_by_pos, fall_by_dst, refill_by_pos, fade_by_pos = collect_animation_maps(world)

    return RenderContext(
        world=world,
        window_width=window_width,
        window_height=window_height,
        tile_size=tile_size,
        board_left=board_left,
        board_bottom=board_bottom,
        board_width=board_width,
        board_height=board_height,
        board_positions=positions,
        swap_by_pos=swap_by_pos,
        fall_by_dst=fall_by_dst,
        refill_by_pos=refill_by_pos,
        fade_by_pos=fade_by_pos,
    )


def collect_animation_maps(
    world: World,
) -> tuple[
    Dict[BoardPos, SwapAnimation],
    Dict[BoardPos, FallAnimation],
    Dict[BoardPos, RefillAnimation],
    Dict[BoardPos, FadeAnimation],
]:
    """Collect animation components into position keyed dictionaries once per frame."""

    swap_by_pos: Dict[BoardPos, SwapAnimation] = {}
    for _, swap in world.get_component(SwapAnimation):
        swap_by_pos[swap.src] = swap
        swap_by_pos[swap.dst] = swap

    fall_by_dst: Dict[BoardPos, FallAnimation] = {}
    for _, fall in world.get_component(FallAnimation):
        fall_by_dst[fall.dst] = fall

    refill_by_pos: Dict[BoardPos, RefillAnimation] = {}
    for _, refill in world.get_component(RefillAnimation):
        refill_by_pos[refill.pos] = refill

    fade_by_pos: Dict[BoardPos, FadeAnimation] = {}
    for _, fade in world.get_component(FadeAnimation):
        fade_by_pos[fade.pos] = fade

    return swap_by_pos, fall_by_dst, refill_by_pos, fade_by_pos
