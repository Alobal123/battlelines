from __future__ import annotations

from typing import Iterable, Sequence

from esper import World

from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.character import Character
from ecs.components.health import Health
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.tile_bank import TileBank
from ecs.factories.abilities import create_ability_by_name

DEFAULT_UNDEAD_FLORIST_LOADOUT: Sequence[str] = (
    "touch_of_undead",
    "poisoned_flower",
)


def _resolve_abilities(world: World, ability_names: Iterable[str]) -> list[int]:
    return [create_ability_by_name(world, name) for name in ability_names]


def create_enemy_undead_florist(
    world: World,
    *,
    ability_names: Iterable[str] | None = None,
    max_hp: int = 30,
) -> int:
    """Spawn the Undead Florist enemy."""

    loadout = tuple(ability_names) if ability_names is not None else DEFAULT_UNDEAD_FLORIST_LOADOUT
    ability_entities = _resolve_abilities(world, loadout)
    enemy_entity = world.create_entity(
        RuleBasedAgent(),
        AbilityListOwner(ability_entities=ability_entities),
        TileBank(owner_entity=0),
        Health(current=max_hp, max_hp=max_hp),
        Character(
            slug="undead_florist",
            name="Undead Florist",
            description="A spectral florist who tends to crimson blooms.",
            portrait_path="undead_florist.png",
        ),
    )
    bank = world.component_for_entity(enemy_entity, TileBank)
    bank.owner_entity = enemy_entity
    return enemy_entity
