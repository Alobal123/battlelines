from esper import World
from ecs.components.animation_swap import SwapAnimation
from ecs.components.animation_fade import FadeAnimation
from ecs.components.animation_fall import FallAnimation
from ecs.components.animation_refill import RefillAnimation
from ecs.components.duration import Duration
from typing import Tuple, List

class AnimationFactory:
    def __init__(self, world: World):
        self.world = world

    def create_swap(self, src: Tuple[int,int], dst: Tuple[int,int], duration: float = 0.2) -> int:
        ent = self.world.create_entity()
        self.world.add_component(ent, SwapAnimation(src=src, dst=dst))
        self.world.add_component(ent, Duration(duration))
        return ent

    def create_fade_group(self, positions: List[Tuple[int,int]], duration: float = 0.2) -> List[int]:
        ents = []
        for pos in positions:
            ent = self.world.create_entity()
            self.world.add_component(ent, FadeAnimation(pos=pos))
            self.world.add_component(ent, Duration(duration))
            ents.append(ent)
        return ents

    def create_fall_group(self, moves: List[dict], duration: float = 0.25) -> List[int]:
        ents = []
        for m in moves:
            ent = self.world.create_entity()
            self.world.add_component(ent, FallAnimation(src=m['from'], dst=m['to']))
            self.world.add_component(ent, Duration(duration))
            ents.append(ent)
        return ents

    def create_refill_group(self, positions: List[Tuple[int,int]], duration: float = 0.25) -> List[int]:
        ents = []
        for pos in positions:
            ent = self.world.create_entity()
            self.world.add_component(ent, RefillAnimation(pos=pos))
            self.world.add_component(ent, Duration(duration))
            ents.append(ent)
        return ents
