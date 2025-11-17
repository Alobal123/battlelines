from __future__ import annotations

from typing import Iterable

from esper import World

from ecs.factories.abilities import create_ability_by_name


def resolve_enemy_abilities(world: World, ability_names: Iterable[str]) -> list[int]:
    """Materialize ability entities for an enemy loadout."""
    return [create_ability_by_name(world, name) for name in ability_names]
