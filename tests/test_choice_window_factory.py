from dataclasses import dataclass

from esper import World

from ecs.components.choice_window import ChoiceOption, ChoiceTag, ChoiceWindow
from ecs.factories.choice_window import (
    ChoiceDefinition,
    clear_choice_window,
    spawn_choice_window,
)


@dataclass
class Marker:
    value: int


def test_spawn_choice_window_creates_entities_and_components():
    world = World()
    choice_a = ChoiceDefinition(label="Alpha", description="First", components=(Marker(1),))
    choice_b = ChoiceDefinition(label="Beta", payload_entity=42, width=300.0)

    window_entity = spawn_choice_window(
        world,
        [choice_a, choice_b],
        skippable=True,
        title="Pick an option",
        panel_width=200.0,
        panel_height=120.0,
    )

    window = world.component_for_entity(window_entity, ChoiceWindow)
    assert window.skippable is True
    assert window.title == "Pick an option"
    assert len(window.option_entities) == 2

    first_entity, second_entity = window.option_entities
    first_option = world.component_for_entity(first_entity, ChoiceOption)
    second_option = world.component_for_entity(second_entity, ChoiceOption)

    assert first_option.order == 0
    assert second_option.order == 1
    assert first_option.width == 200.0
    assert second_option.width == 300.0
    assert first_option.height == 120.0

    assert world.component_for_entity(first_entity, Marker).value == 1
    assert world.has_component(first_entity, ChoiceTag)
    assert world.has_component(second_entity, ChoiceTag)
    assert world.has_component(window_entity, ChoiceTag)


def test_clear_choice_window_removes_all_tagged_entities():
    world = World()
    spawn_choice_window(world, [ChoiceDefinition(label="Only")], skippable=False)

    tagged_entities = [entity for entity, _ in world.get_component(ChoiceTag)]
    assert tagged_entities  # sanity check

    clear_choice_window(world)

    assert not list(world.get_component(ChoiceTag))
    for entity in tagged_entities:
        assert not world.entity_exists(entity)
