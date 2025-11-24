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

DEFAULT_BLOODHOUND_LOADOUT: Sequence[str] = ("scent_lock", "go_for_throat")


def create_enemy_bloodhound(
    world: World,
    *,
    ability_names: Iterable[str] | None = None,
    max_hp: int = 26,
) -> int:
    """Spawn the Bloodhound enemy."""

    loadout = tuple(ability_names) if ability_names is not None else DEFAULT_BLOODHOUND_LOADOUT
    ability_entities = resolve_enemy_abilities(world, loadout)
    enemy_entity = world.create_entity(
        RuleBasedAgent(),
        AbilityListOwner(ability_entities=ability_entities),
        TileBank(owner_entity=0),
        Health(current=max_hp, max_hp=max_hp),
        Affinity(base={"beast": 2, "spirit": 1}),
        Character(
            slug="bloodhound",
            name="Feral Bloodhound",
            description="A relentless tracker with eyes that glow crimson.",
            portrait_path="bloodhound.png",
        ),
    )
    bank = world.component_for_entity(enemy_entity, TileBank)
    bank.owner_entity = enemy_entity
    return enemy_entity
