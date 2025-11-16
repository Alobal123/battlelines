from types import SimpleNamespace

from esper import World

from ecs.components.choice_window import ChoiceWindow, ChoiceOption
from ecs.rendering.choice_window_renderer import ChoiceWindowRenderer


class _StubRenderSystem:
    def __init__(self, world: World) -> None:
        self.world = world


class _HeadlessArcade:
    def __getattr__(self, name):  # pragma: no cover - defensive path
        raise AssertionError(f"Unexpected draw call: {name}")


def test_choice_renderer_updates_layout_in_headless_mode():
    world = World()
    window_entity = world.create_entity()
    world.add_component(
        window_entity,
        ChoiceWindow(option_entities=[], skippable=True, panel_gap=20.0, overlay_color=(1, 2, 3, 4), title="Test"),
    )

    option_entities = []
    for idx in range(2):
        option_entity = world.create_entity()
        world.add_component(
            option_entity,
            ChoiceOption(
                window_entity=window_entity,
                label=f"Option {idx}",
                width=200 + idx * 20,
                height=150,
                order=idx,
            ),
        )
        option_entities.append(option_entity)
    window = world.component_for_entity(window_entity, ChoiceWindow)
    window.option_entities = option_entities

    renderer = ChoiceWindowRenderer(_StubRenderSystem(world))
    ctx = SimpleNamespace(window_width=800.0, window_height=600.0)
    renderer.render(_HeadlessArcade(), ctx, headless=True)

    layout = renderer.option_layout()
    assert set(layout.keys()) == set(option_entities)
    for bounds in layout.values():
        left, bottom, width, height = bounds
        assert bottom < ctx.window_height
        assert width > 0 and height > 0

    first_bounds = layout[option_entities[0]]
    second_bounds = layout[option_entities[1]]
    assert second_bounds[0] > first_bounds[0]
    assert window.skip_button_bounds is not None
    assert renderer.skip_bounds() == window.skip_button_bounds


def test_choice_renderer_clears_layout_when_no_options():
    world = World()
    window_entity = world.create_entity()
    world.add_component(window_entity, ChoiceWindow(option_entities=[]))

    renderer = ChoiceWindowRenderer(_StubRenderSystem(world))
    ctx = SimpleNamespace(window_width=640.0, window_height=480.0)

    renderer.render(_HeadlessArcade(), ctx, headless=True)

    assert not renderer.option_layout()
    window = world.component_for_entity(window_entity, ChoiceWindow)
    assert window.skip_button_bounds is None
