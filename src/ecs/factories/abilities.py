from __future__ import annotations

import importlib
import pkgutil
import random
from typing import Callable, Dict, Iterable, List, Sequence, Set, Tuple, Type, cast

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.game_state import GameMode, GameState
from ecs.components.human_agent import HumanAgent
from ecs.components.starting_ability_choice import AbilityChoice
from ecs.events.bus import EventBus
from ecs.factories.choice_window import ChoiceDefinition, spawn_choice_window
from ecs.systems.ability_pool_system import available_basic_player_ability_names
from ecs.utils.game_state import set_game_mode

ABILITY_FACTORY_PACKAGES: Tuple[str, ...] = (
    "ecs.factories.player_abilities",
    "ecs.factories.player_special_abilities",
    "ecs.factories.enemy_abilities",
)


def _discover_ability_builders() -> Dict[str, Callable[[World], int]]:
    builders: Dict[str, Callable[[World], int]] = {}
    for package_name in ABILITY_FACTORY_PACKAGES:
        package = importlib.import_module(package_name)
        for module in _iter_modules(package_name, package):
            for attr_name in dir(module):
                if not attr_name.startswith("create_ability_"):
                    continue
                factory = getattr(module, attr_name)
                if not callable(factory):
                    continue
                ability_name = attr_name[len("create_ability_") :]
                builders.setdefault(ability_name, cast(Callable[[World], int], factory))
    return builders


def _iter_modules(package_name: str, package) -> Iterable:
    yield package
    package_path = getattr(package, "__path__", None)
    if not package_path:
        return
    for module_info in pkgutil.iter_modules(package_path):
        if module_info.name.startswith("__"):
            continue
        yield importlib.import_module(f"{package_name}.{module_info.name}")


_ABILITY_BUILDERS: Dict[str, Callable[[World], int]] = _discover_ability_builders()

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


def _default_choice_component(owner_entity: int, ability_name: str) -> AbilityChoice:
    return AbilityChoice(owner_entity=owner_entity, ability_name=ability_name)


def spawn_ability_choice_window(
    world: World,
    owner_entity: int,
    ability_names: Sequence[str],
    *,
    event_bus: EventBus | None = None,
    max_options: int = 3,
    title: str = "Choose an Ability",
    rng: random.Random | None = None,
    skippable: bool = False,
    panel_width: float = 260.0,
    panel_height: float = 260.0,
    panel_gap: float = 28.0,
    require_empty_owner: bool = False,
    prevent_duplicate_window: bool = True,
    choice_component_factory: Callable[[int, str], object] | None = None,
    choice_component_type: Type | None = AbilityChoice,
    mode: GameMode | None = GameMode.ABILITY_DRAFT,
    exclude_owned: bool = False,
    press_id: int | None = None,
) -> int | None:
    if max_options <= 0:
        return None
    try:
        owner_comp = world.component_for_entity(owner_entity, AbilityListOwner)
    except KeyError:
        return None
    if require_empty_owner and owner_comp.ability_entities:
        return None
    owned_names: Set[str] = set()
    if exclude_owned:
        owned_names = _owned_ability_names(world, owner_comp)
    component_factory = choice_component_factory or _default_choice_component
    component_type = choice_component_type or AbilityChoice
    if prevent_duplicate_window and component_type is not None:
        if any(True for _ in world.get_component(component_type)):
            return None
    ordered_names = [name for name in ability_names if name and (not exclude_owned or name not in owned_names)]
    if not ordered_names:
        return None
    # Preserve original order for deterministic tests while supporting randomness for gameplay.
    deduped_pool = list(dict.fromkeys(ordered_names))
    if not deduped_pool:
        return None
    generator = rng or random.SystemRandom()
    generator.shuffle(deduped_pool)
    selection = deduped_pool[: min(max_options, len(deduped_pool))]
    if not selection:
        return None
    definitions: List[ChoiceDefinition] = []
    for ability_name in selection:
        label = _format_ability_label(ability_name)
        description, preview_cost = _ability_preview(world, ability_name)
        definitions.append(
            ChoiceDefinition(
                label=label,
                description=description,
                components=(
                    component_factory(owner_entity, ability_name),
                ),
                width=panel_width,
                height=panel_height,
                metadata={"ability_cost": dict(preview_cost)},
            )
        )
    if not definitions:
        return None
    if mode is not None:
        if event_bus is not None:
            set_game_mode(
                world,
                event_bus,
                mode,
                input_guard_press_id=press_id,
            )
        else:
            state_entries = list(world.get_component(GameState))
            if state_entries:
                state_entries[0][1].mode = mode
                state_entries[0][1].input_guard_press_id = press_id
    return spawn_choice_window(
        world,
        definitions,
        skippable=skippable,
        title=title,
        panel_width=panel_width,
        panel_height=panel_height,
        panel_gap=panel_gap,
    )
def spawn_player_ability_choice(
    world: World,
    event_bus: EventBus | None = None,
    *,
    owner_entity: int | None = None,
    rng: random.Random | None = None,
    max_options: int = 3,
    title: str = "Choose an Ability",
    require_empty_owner: bool = False,
    press_id: int | None = None,
) -> int | None:
    if owner_entity is None:
        human_entities = list(world.get_component(HumanAgent))
        if not human_entities:
            return None
        owner_entity = human_entities[0][0]
    available_names = available_basic_player_ability_names(world, owner_entity)
    if not available_names:
        return None
    return spawn_ability_choice_window(
        world,
        owner_entity=owner_entity,
        ability_names=available_names,
        event_bus=event_bus,
        title=title,
        rng=rng,
        max_options=max_options,
        require_empty_owner=require_empty_owner,
        exclude_owned=True,
        press_id=press_id,
    )


def _format_ability_label(ability_name: str) -> str:
    return ability_name.replace("_", " ").title()


_ABILITY_PREVIEW_CACHE: Dict[str, tuple[str, Tuple[tuple[str, int], ...]]] = {}


def _ability_preview(world: World, ability_name: str) -> tuple[str, Dict[str, int]]:
    cached = _ABILITY_PREVIEW_CACHE.get(ability_name)
    if cached is not None:
        description, cost_tuples = cached
        return description, dict(cost_tuples)
    temp_entity = create_ability_by_name(world, ability_name)
    try:
        ability = world.component_for_entity(temp_entity, Ability)
        description = ability.description or ""
        cost_items = tuple(sorted((ability.cost or {}).items()))
    except KeyError:
        description = ""
        cost_items = ()
    finally:
        try:
            world.delete_entity(temp_entity, immediate=True)
        except Exception:
            world.delete_entity(temp_entity)
    _ABILITY_PREVIEW_CACHE[ability_name] = (description, cost_items)
    return description, dict(cost_items)


def _ability_description(world: World, ability_name: str) -> str:
    description, _ = _ability_preview(world, ability_name)
    return description


def _owned_ability_names(world: World, owner: AbilityListOwner) -> Set[str]:
    owned: Set[str] = set()
    for ability_entity in owner.ability_entities:
        try:
            ability = world.component_for_entity(ability_entity, Ability)
        except KeyError:
            continue
        if ability.name:
            owned.add(ability.name)
    return owned
