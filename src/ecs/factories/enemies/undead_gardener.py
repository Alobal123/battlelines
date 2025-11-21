from __future__ import annotations

from typing import Iterable, Sequence

from esper import World

from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.character import Character
from ecs.components.health import Health
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.tile_bank import TileBank
from ecs.components.affinity import Affinity
from .common import resolve_enemy_abilities

DEFAULT_UNDEAD_GARDENER_LOADOUT: Sequence[str] = (
    "touch_of_undead",
    "shovel_punch",
)


def create_enemy_undead_gardener(
    world: World,
    *,
    ability_names: Iterable[str] | None = None,
    max_hp: int = 30,
) -> int:
    """Spawn the Undead Gardener enemy."""

    loadout = tuple(ability_names) if ability_names is not None else DEFAULT_UNDEAD_GARDENER_LOADOUT
    ability_entities = resolve_enemy_abilities(world, loadout)
    enemy_entity = world.create_entity(
        RuleBasedAgent(),
        AbilityListOwner(ability_entities=ability_entities),
        TileBank(owner_entity=0),
        Health(current=max_hp, max_hp=max_hp),
        Affinity(base={"nature": 1, "spirit": 1}),
        Character(
            slug="undead_gardener",
            name="Undead Gardener",
            description="A mysterious caretaker of forgotten groves",
            portrait_path="undead_gardener.png",
        ),
    )
    bank = world.component_for_entity(enemy_entity, TileBank)
    bank.owner_entity = enemy_entity
    return enemy_entity
