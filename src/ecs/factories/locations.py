from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, List, Mapping, Sequence

from esper import World

from ecs.components.game_state import GameMode, GameState
from ecs.components.location import LocationChoice
from ecs.events.bus import EventBus
from ecs.factories.choice_window import ChoiceDefinition, spawn_choice_window
from ecs.utils.game_state import set_game_mode


@dataclass(frozen=True)
class LocationSpec:
    slug: str
    name: str
    description: str
    enemy_names: Sequence[str]


_LOCATION_SPECS: Mapping[str, LocationSpec] = {
    "skeletal_garden": LocationSpec(
        slug="skeletal_garden",
        name="Skeletal Garden",
        description="Twisting bone-white flora tended by restless spirits.",
        enemy_names=("undead_beekeeper", "undead_gardener", "undead_florist"),
    ),
}


def all_location_specs() -> Iterable[LocationSpec]:
    return _LOCATION_SPECS.values()


def get_location_spec(slug: str) -> LocationSpec | None:
    return _LOCATION_SPECS.get(slug)


def spawn_location_choice_window(
    world: World,
    owner_entity: int,
    *,
    event_bus: EventBus | None = None,
    title: str = "Choose a Destination",
    rng: random.Random | None = None,
    press_id: int | None = None,
    panel_width: float = 280.0,
    panel_height: float = 240.0,
    panel_gap: float = 32.0,
) -> int | None:
    specs = list(all_location_specs())
    if not specs:
        return None
    generator = rng or random.SystemRandom()
    generator.shuffle(specs)
    definitions: List[ChoiceDefinition] = []
    for spec in specs:
        definitions.append(
            ChoiceDefinition(
                label=spec.name,
                description=spec.description,
                components=(LocationChoice(owner_entity=owner_entity, location_slug=spec.slug),),
                width=panel_width,
                height=panel_height,
            )
        )
    if not definitions:
        return None
    if event_bus is not None:
        set_game_mode(world, event_bus, GameMode.LOCATION_DRAFT, input_guard_press_id=press_id)
    else:
        entries = list(world.get_component(GameState))
        if entries:
            entries[0][1].mode = GameMode.LOCATION_DRAFT
            entries[0][1].input_guard_press_id = press_id
    return spawn_choice_window(
        world,
        definitions,
        skippable=False,
        title=title,
        panel_width=panel_width,
        panel_height=panel_height,
        panel_gap=panel_gap,
    )
