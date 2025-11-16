from __future__ import annotations

from typing import Callable, Dict, List, Tuple

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.game_state import GameMode, GameState
from ecs.components.human_agent import HumanAgent
from ecs.components.starting_ability_choice import StartingAbilityChoice
from ecs.factories.choice_window import ChoiceDefinition, spawn_choice_window
from ecs.factories.player_abilities import (
    create_ability_blood_bolt,
    create_ability_savagery,
    create_ability_spirit_leech,
    create_ability_verdant_touch,
)
from ecs.factories.player_special_abilities import (
    create_ability_crimson_pulse,
    create_ability_tactical_shift,
)
from ecs.factories.enemy_abilities import (
    create_ability_shovel_punch,
    create_ability_touch_of_undead,
)
from ecs.systems.ability_pool_system import available_basic_player_ability_names


_ABILITY_BUILDERS: Dict[str, Callable[[World], int]] = {
    "tactical_shift": create_ability_tactical_shift,
    "crimson_pulse": create_ability_crimson_pulse,
    "savagery": create_ability_savagery,
    "spirit_leech": create_ability_spirit_leech,
    "verdant_touch": create_ability_verdant_touch,
    "blood_bolt": create_ability_blood_bolt,
    "shovel_punch": create_ability_shovel_punch,
    "touch_of_undead": create_ability_touch_of_undead,
}

_DEFAULT_ABILITY_ORDER: Tuple[str, ...] = (
    "tactical_shift",
    "crimson_pulse",
    "savagery",
    "verdant_touch",
    "blood_bolt",
)


def create_default_player_abilities(world: World) -> List[int]:
    """Create the standard player ability loadout."""
    return [create_ability_by_name(world, name) for name in _DEFAULT_ABILITY_ORDER]


def create_ability_by_name(world: World, name: str) -> int:
    try:
        builder = _ABILITY_BUILDERS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown ability '{name}'") from exc
    return builder(world)


def spawn_starting_ability_choice(world: World) -> int | None:
    """Spawn a choice window that lets the human player pick a starting ability.

    Ability options are sourced from the dynamic ability pool to ensure future
    abilities are automatically included without updating static metadata.
    """
    human_entities = list(world.get_component(HumanAgent))
    if not human_entities:
        return None
    owner_entity = human_entities[0][0]
    try:
        owner_comp = world.component_for_entity(owner_entity, AbilityListOwner)
    except KeyError:
        return None
    if owner_comp.ability_entities:
        return None
    if any(True for _ in world.get_component(StartingAbilityChoice)):
        return None
    available_names = available_basic_player_ability_names(world, owner_entity)
    if not available_names:
        return None
    selection = available_names[:3]
    definitions: List[ChoiceDefinition] = []
    for ability_name in selection:
        label = _format_ability_label(ability_name)
        description = _ability_description(world, ability_name)
        definitions.append(
            ChoiceDefinition(
                label=label,
                description=description,
                components=(
                    StartingAbilityChoice(owner_entity=owner_entity, ability_name=ability_name),
                ),
                width=260.0,
                height=180.0,
            )
        )
    if not definitions:
        return None
    state_entries = list(world.get_component(GameState))
    if state_entries:
        state_entries[0][1].mode = GameMode.ABILITY_DRAFT
    return spawn_choice_window(
        world,
        definitions,
        skippable=False,
        title="Choose Your First Ability",
        panel_width=260.0,
        panel_height=180.0,
        panel_gap=28.0,
    )


def _format_ability_label(ability_name: str) -> str:
    return ability_name.replace("_", " ").title()


_ABILITY_DESCRIPTION_CACHE: Dict[str, str] = {}


def _ability_description(world: World, ability_name: str) -> str:
    cached = _ABILITY_DESCRIPTION_CACHE.get(ability_name)
    if cached is not None:
        return cached
    temp_entity = create_ability_by_name(world, ability_name)
    try:
        ability = world.component_for_entity(temp_entity, Ability)
        description = ability.description or ""
    except KeyError:
        description = ""
    finally:
        try:
            world.delete_entity(temp_entity, immediate=True)
        except Exception:
            world.delete_entity(temp_entity)
    _ABILITY_DESCRIPTION_CACHE[ability_name] = description
    return description
