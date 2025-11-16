"""Factory helpers for creating configurable choice windows."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from esper import World

from ecs.components.choice_window import ChoiceOption, ChoiceTag, ChoiceWindow


@dataclass
class ChoiceDefinition:
    """Specification for a single choice option."""

    label: str
    description: str = ""
    components: Sequence[object] = field(default_factory=tuple)
    payload_entity: int | None = None
    width: float | None = None
    height: float | None = None


def spawn_choice_window(
    world: World,
    choices: Iterable[ChoiceDefinition],
    *,
    skippable: bool = False,
    title: str | None = None,
    panel_width: float = 240.0,
    panel_height: float = 160.0,
    panel_gap: float = 24.0,
) -> int:
    """Create a choice window entity with the provided options."""
    choice_defs = list(choices)
    window_entity = world.create_entity()
    option_entities: list[int] = []

    for idx, choice in enumerate(choice_defs):
        option_entity = world.create_entity()
        option = ChoiceOption(
            window_entity=window_entity,
            label=choice.label,
            description=choice.description,
            payload_entity=choice.payload_entity,
            width=choice.width or panel_width,
            height=choice.height or panel_height,
            order=idx,
        )
        world.add_component(option_entity, option)
        world.add_component(option_entity, ChoiceTag())
        for component in choice.components:
            world.add_component(option_entity, component)
        option_entities.append(option_entity)

    window = ChoiceWindow(
        option_entities=option_entities,
        skippable=skippable,
        title=title,
        panel_gap=panel_gap,
    )
    world.add_component(window_entity, window)
    world.add_component(window_entity, ChoiceTag())
    return window_entity


def clear_choice_window(world: World) -> None:
    """Remove all entities tagged for the current choice window, if any."""
    tagged_entities = [ent for ent, _ in world.get_component(ChoiceTag)]
    for ent in tagged_entities:
        world.delete_entity(ent, immediate=True)