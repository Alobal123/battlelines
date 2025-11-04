"""Entry point for the Battlelines match-three prototype.

Sets up ECS world, event bus, systems, and Arcade window.
"""
from arcade import Window, run, set_background_color, color
from ecs.world import create_world
from ecs.events.bus import EventBus, EVENT_MOUSE_PRESS
from ecs.systems.render import RenderSystem
from ecs.systems.animation import AnimationSystem
from ecs.systems.board import BoardSystem
from ecs.systems.input import InputSystem
from ecs.systems.match import MatchSystem
from ecs.systems.match_resolution import MatchResolutionSystem
from ecs.constants import GRID_ROWS, GRID_COLS, TILE_SIZE, BOTTOM_MARGIN

class BattlelinesWindow(Window):
    def __init__(self):
        super().__init__(800, 600, "Battlelines")
        self.set_update_rate(1/60)
        self.event_bus = EventBus()
        self.world = create_world(self.event_bus)
        self.board_system = BoardSystem(self.world, self.event_bus)
        self.match_system = MatchSystem(self.world, self.event_bus)
        self.animation_system = AnimationSystem(self.world, self.event_bus)
        self.render_system = RenderSystem(self.world, self.event_bus, self)
        self.match_resolution_system = MatchResolutionSystem(self.world, self.event_bus)
        # InputSystem expects (event_bus, window)
        self.input_system = InputSystem(self.event_bus, self)
        set_background_color(color.BLACK)

    def on_draw(self):
        self.clear()
        self.render_system.process()

    def on_update(self, delta_time: float):
        self.event_bus.emit('tick', dt=delta_time)

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        self.event_bus.emit(EVENT_MOUSE_PRESS, x=x, y=y, button=button)


def main():
    window = BattlelinesWindow()
    run()

if __name__ == "__main__":
    main()
