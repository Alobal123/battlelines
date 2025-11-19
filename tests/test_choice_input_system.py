from esper import World

from ecs.components.choice_window import ChoiceOption, ChoiceWindow
from ecs.components.game_state import GameMode
from ecs.events.bus import (
    EVENT_CHOICE_SELECTED,
    EVENT_CHOICE_SKIPPED,
    EVENT_MOUSE_PRESS,
    EVENT_GAME_MODE_CHANGED,
    EventBus,
)
from ecs.systems.choice_input_system import ChoiceInputSystem


def _build_window(world: World, *, skippable: bool = False):
    window_entity = world.create_entity()
    world.add_component(window_entity, ChoiceWindow(option_entities=[], skippable=skippable))
    option_entity = world.create_entity()
    option = ChoiceOption(
        window_entity=window_entity,
        label="Opt",
        bounds=(10.0, 20.0, 100.0, 100.0),
        order=0,
    )
    world.add_component(option_entity, option)
    window = world.component_for_entity(window_entity, ChoiceWindow)
    window.option_entities = [option_entity]
    return window_entity, option_entity


def test_choice_input_emits_selection_event():
    world = World()
    event_bus = EventBus()
    window_entity, option_entity = _build_window(world)
    choice_input = ChoiceInputSystem(world, event_bus)

    captured = {}

    def handler(sender, **payload):
        captured.update(payload)

    event_bus.subscribe(EVENT_CHOICE_SELECTED, handler)

    event_bus.emit(EVENT_MOUSE_PRESS, x=50, y=50, button=1, press_id=101)

    assert captured["choice_entity"] == option_entity
    assert captured["window_entity"] == window_entity
    assert captured["press_id"] == 101


def test_choice_input_emits_skip_event():
    world = World()
    event_bus = EventBus()
    window_entity, _ = _build_window(world, skippable=True)
    window = world.component_for_entity(window_entity, ChoiceWindow)
    window.skip_button_bounds = (20.0, 0.0, 80.0, 30.0)
    choice_input = ChoiceInputSystem(world, event_bus)

    captured = {}

    def handler(sender, **payload):
        captured.update(payload)

    event_bus.subscribe(EVENT_CHOICE_SKIPPED, handler)

    event_bus.emit(EVENT_MOUSE_PRESS, x=40, y=5, button=1, press_id=202)

    assert captured["window_entity"] == window_entity
    assert captured["press_id"] == 202


def test_choice_input_ignores_other_buttons():
    world = World()
    event_bus = EventBus()
    _build_window(world)
    choice_input = ChoiceInputSystem(world, event_bus)

    received = {}
    event_bus.subscribe(EVENT_CHOICE_SELECTED, lambda sender, **payload: received.update(payload))

    event_bus.emit(EVENT_MOUSE_PRESS, x=50, y=50, button=2, press_id=303)

    assert not received


def test_choice_input_respects_press_guard():
    world = World()
    event_bus = EventBus()
    window_entity, _ = _build_window(world)
    choice_input = ChoiceInputSystem(world, event_bus)

    captured = {}
    event_bus.subscribe(EVENT_CHOICE_SELECTED, lambda sender, **payload: captured.update(payload))

    event_bus.emit(
        EVENT_GAME_MODE_CHANGED,
        previous_mode=GameMode.MENU,
        new_mode=GameMode.ABILITY_DRAFT,
        input_guard_press_id=900,
    )

    event_bus.emit(EVENT_MOUSE_PRESS, x=50, y=50, button=1, press_id=900)
    assert not captured

    event_bus.emit(EVENT_MOUSE_PRESS, x=50, y=50, button=1, press_id=901)
    assert captured["window_entity"] == window_entity
