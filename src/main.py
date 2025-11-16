"""Entry point for the Battlelines match-three prototype.

Sets up ECS world, event bus, systems, and Arcade window.
"""
from arcade import Window, run, set_background_color, color, key
from ecs.world import create_world
from ecs.constants import GRID_ROWS, GRID_COLS
from ecs.events.bus import EVENT_TICK, EventBus, EVENT_MOUSE_PRESS, EVENT_MOUSE_MOVE
from ecs.components.game_state import GameState, GameMode
from ecs.menu.factory import spawn_main_menu
from ecs.menu.render_system import MenuRenderSystem
from ecs.menu.input_system import MenuInputSystem
from ecs.systems.choice_input_system import ChoiceInputSystem
from ecs.systems.ability_starting_system import AbilityStartingSystem
from ecs.systems.render import RenderSystem
from ecs.systems.animation import AnimationSystem
from ecs.systems.board import BoardSystem
from ecs.systems.input import InputSystem
from ecs.systems.match import MatchSystem
from ecs.systems.match_resolution import MatchResolutionSystem
from ecs.systems.tile_bank_system import TileBankSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.ability_targeting_system import AbilityTargetingSystem
from ecs.systems.turn_system import TurnSystem
from ecs.systems.health_system import HealthSystem
from ecs.systems.effects.damage_effect_system import DamageEffectSystem
from ecs.systems.effects.heal_effect_system import HealEffectSystem
from ecs.systems.effects.board_clear_effect_system import BoardClearEffectSystem
from ecs.systems.effects.board_transform_effect_system import BoardTransformEffectSystem
from ecs.systems.tooltip_system import TooltipSystem
from ecs.systems.rule_based_ai_system import RuleBasedAISystem

class BattlelinesWindow(Window):
    def __init__(self):
        super().__init__(800, 600, "Witchfire")
        self.set_update_rate(1/60)
        self.event_bus = EventBus()
        self.world = create_world(
            self.event_bus,
            initial_mode=GameMode.MENU,
            grant_default_player_abilities=False,
        )
        spawn_main_menu(self.world, self.width, self.height)
        self.menu_render_system = MenuRenderSystem(self.world, self)
        self.menu_input_system = MenuInputSystem(self.world, self.event_bus)
        self.choice_input_system = ChoiceInputSystem(self.world, self.event_bus)
        self.ability_starting_system = AbilityStartingSystem(
            self.world,
            self.event_bus,
        )
        self.render_system = RenderSystem(self.world, self.event_bus, self)
        self.tooltip_system = TooltipSystem(self.world, self.event_bus, self, self.render_system)
        self.input_system = InputSystem(self.event_bus, self, self.world)

        # Combat systems exist up front but self-regulate based on GameMode.
        self.board_system = BoardSystem(self.world, self.event_bus, rows=GRID_ROWS, cols=GRID_COLS)
        self.match_system = MatchSystem(self.world, self.event_bus)
        self.animation_system = AnimationSystem(self.world, self.event_bus)
        self.match_resolution_system = MatchResolutionSystem(self.world, self.event_bus)
        self.tile_bank_system = TileBankSystem(self.world, self.event_bus)
        self.effect_lifecycle_system = EffectLifecycleSystem(self.world, self.event_bus)
        self.damage_effect_system = DamageEffectSystem(self.world, self.event_bus)
        self.heal_effect_system = HealEffectSystem(self.world, self.event_bus)
        self.board_clear_effect_system = BoardClearEffectSystem(self.world, self.event_bus)
        self.board_transform_effect_system = BoardTransformEffectSystem(self.world, self.event_bus)
        self.ability_targeting_system = AbilityTargetingSystem(self.world, self.event_bus)
        self.ability_system = AbilitySystem(self.world, self.event_bus)
        self.turn_system = TurnSystem(self.world, self.event_bus)
        self.rule_based_ai_system = RuleBasedAISystem(self.world, self.event_bus)
        self.health_system = HealthSystem(self.world, self.event_bus)
        set_background_color(color.BLACK)
        # Toggle fullscreen and allow dynamic scaling; width/height update after fullscreen set.
        try:
            self.set_fullscreen(True)
        except Exception:
            # Headless test environments may fail; ignore.
            pass

    def on_resize(self, width: int, height: int):
        # Propagate resize to render system for recalculating layout
        if hasattr(self.render_system, 'notify_resize'):
            self.render_system.notify_resize(width, height)
        return super().on_resize(width, height)

    def on_draw(self):
        self.clear()
        state = self._get_game_state()
        if state and state.mode == GameMode.MENU:
            self.menu_render_system.process()
        else:
            self.render_system.process()

    def on_update(self, delta_time: float):
        state = self._get_game_state()
        if state and state.mode == GameMode.COMBAT:
            self.event_bus.emit(EVENT_TICK, dt=delta_time)

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        self.event_bus.emit(EVENT_MOUSE_PRESS, x=x, y=y, button=button)

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float):
        state = self._get_game_state()
        if state and state.mode == GameMode.COMBAT:
            self.event_bus.emit(EVENT_MOUSE_MOVE, x=x, y=y, dx=dx, dy=dy)

    def on_key_press(self, symbol: int, modifiers: int):
        state = self._get_game_state()
        if state and state.mode == GameMode.MENU:
            self.menu_input_system.handle_key_press(symbol, modifiers)

    def _get_game_state(self) -> GameState | None:
        for _, state in self.world.get_component(GameState):
            return state
        return None

def main():
    window = BattlelinesWindow()
    run()

if __name__ == "__main__":
    main()
