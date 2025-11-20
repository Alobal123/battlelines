from __future__ import annotations

import importlib
import pkgutil
import random
from typing import Callable, Dict, Iterable, List, Sequence, Set, Tuple, Type, cast

from esper import World

from ecs.components.game_state import GameMode, GameState
from ecs.components.human_agent import HumanAgent
from ecs.components.skill import Skill
from ecs.components.skill_list_owner import SkillListOwner
from ecs.components.skill_effect import SkillEffects
from ecs.components.starting_skill_choice import SkillChoice
from ecs.events.bus import EventBus
from ecs.factories.choice_window import ChoiceDefinition, spawn_choice_window
from ecs.utils.game_state import set_game_mode

SKILL_FACTORY_PACKAGES: Tuple[str, ...] = (
    "ecs.factories.player_skills",
)


def _discover_skill_builders() -> Dict[str, Callable[[World], int]]:
    builders: Dict[str, Callable[[World], int]] = {}
    for package_name in SKILL_FACTORY_PACKAGES:
        package = importlib.import_module(package_name)
        for module in _iter_modules(package_name, package):
            for attr_name in dir(module):
                if not attr_name.startswith("create_skill_"):
                    continue
                factory = getattr(module, attr_name)
                if not callable(factory):
                    continue
                skill_name = attr_name[len("create_skill_") :]
                builders.setdefault(skill_name, cast(Callable[[World], int], factory))
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


_SKILL_BUILDERS: Dict[str, Callable[[World], int]] = _discover_skill_builders()


def discover_player_skill_names() -> Sequence[str]:
    return tuple(sorted(_SKILL_BUILDERS.keys()))


def create_skill_by_name(world: World, name: str) -> int:
    try:
        builder = _SKILL_BUILDERS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown skill '{name}'") from exc
    return builder(world)


def _default_choice_component(owner_entity: int, skill_name: str) -> SkillChoice:
    return SkillChoice(owner_entity=owner_entity, skill_name=skill_name)


def available_player_skill_names(world: World, owner_entity: int) -> List[str]:
    names = discover_player_skill_names()
    owned = _owned_skill_names(world, owner_entity)
    return [name for name in names if name not in owned]


def spawn_skill_choice_window(
    world: World,
    owner_entity: int,
    skill_names: Sequence[str],
    *,
    event_bus: EventBus | None = None,
    max_options: int = 3,
    title: str = "Choose a Skill",
    rng: random.Random | None = None,
    skippable: bool = False,
    panel_width: float = 260.0,
    panel_height: float = 180.0,
    panel_gap: float = 28.0,
    prevent_duplicate_window: bool = True,
    choice_component_factory: Callable[[int, str], object] | None = None,
    choice_component_type: Type | None = SkillChoice,
    mode: GameMode | None = GameMode.SKILL_DRAFT,
    press_id: int | None = None,
) -> int | None:
    if max_options <= 0:
        return None
    ordered_names = [name for name in skill_names if name]
    if not ordered_names:
        return None
    if prevent_duplicate_window and choice_component_type is not None:
        if any(True for _ in world.get_component(choice_component_type)):
            return None
    deduped_pool = list(dict.fromkeys(ordered_names))
    if not deduped_pool:
        return None
    generator = rng or random.SystemRandom()
    generator.shuffle(deduped_pool)
    selection = deduped_pool[: min(max_options, len(deduped_pool))]
    if not selection:
        return None
    definitions: List[ChoiceDefinition] = []
    component_factory = choice_component_factory or _default_choice_component
    for skill_name in selection:
        label = _format_skill_label(skill_name)
        description = _skill_description(world, skill_name)
        definitions.append(
            ChoiceDefinition(
                label=label,
                description=description,
                components=(component_factory(owner_entity, skill_name),),
                width=panel_width,
                height=panel_height,
            )
        )
    if not definitions:
        return None
    if mode is not None:
        if event_bus is not None:
            set_game_mode(world, event_bus, mode, input_guard_press_id=press_id)
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


def spawn_player_skill_choice(
    world: World,
    event_bus: EventBus | None = None,
    *,
    owner_entity: int | None = None,
    rng: random.Random | None = None,
    max_options: int = 3,
    title: str = "Choose a Skill",
    press_id: int | None = None,
) -> int | None:
    if owner_entity is None:
        human_entities = list(world.get_component(HumanAgent))
        if not human_entities:
            return None
        owner_entity = human_entities[0][0]
    available_names = available_player_skill_names(world, owner_entity)
    if not available_names:
        return None
    return spawn_skill_choice_window(
        world,
        owner_entity=owner_entity,
        skill_names=available_names,
        event_bus=event_bus,
        rng=rng,
        max_options=max_options,
        title=title,
        press_id=press_id,
    )


def _format_skill_label(skill_name: str) -> str:
    return skill_name.replace("_", " ").title()


_SKILL_DESCRIPTION_CACHE: Dict[str, str] = {}


def _skill_description(world: World, skill_name: str) -> str:
    cached = _SKILL_DESCRIPTION_CACHE.get(skill_name)
    if cached is not None:
        return cached
    temp_entity = create_skill_by_name(world, skill_name)
    try:
        skill = world.component_for_entity(temp_entity, Skill)
        description = skill.description or ""
    except KeyError:
        description = ""
    finally:
        try:
            world.delete_entity(temp_entity, immediate=True)
        except Exception:
            world.delete_entity(temp_entity)
    _SKILL_DESCRIPTION_CACHE[skill_name] = description
    return description


def _owned_skill_names(world: World, owner_entity: int) -> Set[str]:
    try:
        skill_list: SkillListOwner = world.component_for_entity(owner_entity, SkillListOwner)
    except KeyError:
        return set()
    owned: Set[str] = set()
    for skill_entity in list(skill_list.skill_entities):
        owned.update(skill_slugs_for_entity(world, skill_entity))
    return owned


def skill_slugs_for_entity(world: World, skill_entity: int) -> Set[str]:
    slugs: Set[str] = set()
    try:
        effects: SkillEffects | None = world.component_for_entity(skill_entity, SkillEffects)
    except KeyError:
        effects = None
    if effects is not None:
        for spec in effects.effects:
            if spec.slug:
                slugs.add(spec.slug)
    try:
        skill = world.component_for_entity(skill_entity, Skill)
    except KeyError:
        skill = None
    if skill is not None and skill.name:
        slugs.add(_normalize_skill_slug(skill.name))
    return slugs


def _normalize_skill_slug(name: str) -> str:
    return name.strip().lower().replace(" ", "_")
