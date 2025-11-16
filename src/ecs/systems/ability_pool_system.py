from __future__ import annotations

import importlib
import pkgutil
from typing import List, Sequence, Set

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_POOL_OFFER,
    EVENT_ABILITY_POOL_REQUEST,
)

_BASIC_ABILITY_NAMES: Sequence[str] | None = None


def discover_basic_player_ability_names() -> Sequence[str]:
    """Return the canonical set of basic player ability names."""
    global _BASIC_ABILITY_NAMES
    if _BASIC_ABILITY_NAMES is not None:
        return _BASIC_ABILITY_NAMES

    from ecs.factories import player_abilities as ability_package

    names: Set[str] = set()
    package_name = ability_package.__name__
    package_path = getattr(ability_package, "__path__", None)
    if package_path:
        for module_info in pkgutil.iter_modules(package_path):
            if module_info.name.startswith("__"):
                continue
            module = importlib.import_module(f"{package_name}.{module_info.name}")
            names.update(_extract_ability_names_from_module(module))
    names.update(_extract_ability_names_from_module(ability_package))
    _BASIC_ABILITY_NAMES = tuple(sorted(names))
    return _BASIC_ABILITY_NAMES


def _extract_ability_names_from_module(module) -> Set[str]:
    names: Set[str] = set()
    for attr_name, attr_value in vars(module).items():
        if not attr_name.startswith("create_ability_"):
            continue
        if callable(attr_value):
            ability_name = attr_name[len("create_ability_") :]
            if ability_name:
                names.add(ability_name)
    return names


def owned_basic_player_ability_names(world: World, owner_entity: int) -> Set[str]:
    owned: Set[str] = set()
    try:
        owner = world.component_for_entity(owner_entity, AbilityListOwner)
    except KeyError:
        return owned
    for ability_entity in owner.ability_entities:
        try:
            ability = world.component_for_entity(ability_entity, Ability)
        except KeyError:
            continue
        if ability.name:
            owned.add(ability.name)
    return owned


def available_basic_player_ability_names(world: World, owner_entity: int) -> List[str]:
    ability_names = discover_basic_player_ability_names()
    owned = owned_basic_player_ability_names(world, owner_entity)
    if not owned:
        return list(ability_names)
    return [name for name in ability_names if name not in owned]


class AbilityPoolSystem:
    """Serves ability offers based on the pool of basic player abilities."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self._ability_names: Sequence[str] = discover_basic_player_ability_names()
        self.event_bus.subscribe(EVENT_ABILITY_POOL_REQUEST, self._on_pool_request)

    def _on_pool_request(self, sender, **payload) -> None:
        owner_entity = payload.get("owner_entity")
        count = payload.get("count")
        request_id = payload.get("request_id")
        if owner_entity is None:
            return
        try:
            count_int = int(count)
        except (TypeError, ValueError):
            return
        if count_int <= 0:
            return
        available = available_basic_player_ability_names(self.world, owner_entity)
        offers = list(available[:count_int])
        self.event_bus.emit(
            EVENT_ABILITY_POOL_OFFER,
            owner_entity=owner_entity,
            abilities=offers,
            request_id=request_id,
        )

    def known_ability_names(self) -> Sequence[str]:
        """Expose discovered ability names for tests or debug tooling."""
        return self._ability_names
