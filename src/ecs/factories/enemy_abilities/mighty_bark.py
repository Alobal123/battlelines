from __future__ import annotations

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_cooldown import AbilityCooldown
from ecs.components.ability_target import AbilityTarget


def create_ability_mighty_bark(world: World) -> int:
    """Draw strength from each guarded tile to heal the pack."""
    return world.create_entity(
        Ability(
            name="mighty_bark",
            kind="active",
            cost={"spirit": 4, "nature": 2},
            description="Heal 1 for every tile currently guarded by the mastiffs.",
            cooldown=0,
            params={"heal_per_tile": 1},
        ),
        AbilityTarget(target_type="self", max_targets=0),
        AbilityCooldown(),
    )
