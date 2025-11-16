from __future__ import annotations

from typing import Callable, Dict, List, Tuple

from esper import World

from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.game_state import GameMode, GameState
from ecs.components.human_agent import HumanAgent
from ecs.components.starting_ability_choice import StartingAbilityChoice
from ecs.factories.choice_window import ChoiceDefinition, spawn_choice_window
from ecs.factories.player_abilities import (
    create_ability_blood_bolt,
    create_ability_savagery,
    create_ability_verdant_touch,
)
from ecs.factories.player_special_abilities import (
    create_ability_crimson_pulse,
    create_ability_tactical_shift,
)
from ecs.factories.enemy_abilities import create_ability_shovel_punch


_ABILITY_BUILDERS: Dict[str, Callable[[World], int]] = {
    "tactical_shift": create_ability_tactical_shift,
    "crimson_pulse": create_ability_crimson_pulse,
    "savagery": create_ability_savagery,
    "verdant_touch": create_ability_verdant_touch,
    "blood_bolt": create_ability_blood_bolt,
    "shovel_punch": create_ability_shovel_punch,
}

_DEFAULT_ABILITY_ORDER: Tuple[str, ...] = (
    "tactical_shift",
    "crimson_pulse",
    "savagery",
    "verdant_touch",
    "blood_bolt",
)

_STARTING_CHOICES: Tuple[Tuple[str, str, str], ...] = (
    ("verdant_touch", "Verdant Touch", "Heal 4 HP."),
    ("blood_bolt", "Blood Bolt", "Deal 2 damage to yourself and 6 damage to the opponent."),
    ("savagery", "Savagery", "Gain +1 damage to all attacks for three turns."),
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
    """Spawn a choice window that lets the human player pick a starting ability."""
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
    definitions: List[ChoiceDefinition] = []
    for ability_name, label, description in _STARTING_CHOICES:
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
