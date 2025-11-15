from __future__ import annotations

import random
from typing import Dict, Optional, Tuple, cast

from esper import World

from ecs.ai.simulation import CloneState
from ecs.components.active_switch import ActiveSwitch
from ecs.components.ability_cooldown import AbilityCooldown
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.health import Health
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.tile import TileType
from ecs.components.tile_bank import TileBank
from ecs.events.bus import EventBus
from ecs.systems.base_ai_system import (
    ActionPayload,
    AbilityAction,
    AbilitySnapshot,
    BaseAISystem,
    OwnerSnapshot,
)


class RuleBasedAISystem(BaseAISystem):
    """Scores actions according to prioritised tactical heuristics."""

    def __init__(
        self,
        world: World,
        event_bus: EventBus,
        rng: Optional[random.Random] = None,
    ) -> None:
        super().__init__(world, event_bus, RuleBasedAgent, rng)

    def _score_clone_world(
        self,
        clone_state: CloneState,
        owner_entity: int,
        snapshot: OwnerSnapshot,
        candidate: Tuple[str, ActionPayload],
    ) -> float:
        clone_world = clone_state.world
        base_witchfire = self._count_active_witchfire(self.world)
        post_witchfire = self._count_active_witchfire(clone_world)
        witchfire_cleared = max(0, base_witchfire - post_witchfire)
        kill_flag = 1 if self._any_opponent_defeated(clone_world, owner_entity) else 0
        ability_usage_flag = 1 if candidate[0] == "ability" else 0
        ability_cost_total = 0
        if candidate[0] == "ability":
            ability_action = cast(AbilityAction, candidate[1])
            ability_cost_total = self._ability_cost_total(snapshot, ability_action)
        clone_bank_counts = self._clone_bank_counts(clone_world, owner_entity)
        baseline_deficits = self._compute_mana_deficits(snapshot.bank_counts, snapshot.ability_map)
        clone_deficits = self._compute_mana_deficits(clone_bank_counts, snapshot.ability_map, clone_state)
        needed_mana_delta = max(0, sum(baseline_deficits.values()) - sum(clone_deficits.values()))
        other_mana_gain, secrets_gain = self._compute_bank_gains(
            snapshot.bank_counts,
            clone_bank_counts,
            baseline_deficits,
        )
        new_affordable = self._count_new_affordable(clone_state, owner_entity, snapshot, clone_bank_counts)
        score = (
            kill_flag * 1_000_000_000
            + witchfire_cleared * 1_000_000
            + ability_usage_flag * 100_000
            + ability_cost_total * 10_000
            + new_affordable * 1_000
            + needed_mana_delta * 100
            + other_mana_gain * 10
            + secrets_gain
            + self.random.random() * 0.001
        )
        return score

    def _any_opponent_defeated(self, world: World, owner_entity: int) -> bool:
        # Consider only controller entities with abilities.
        opponents = {
            ent for ent, _ in world.get_component(AbilityListOwner) if ent != owner_entity
        }
        if not opponents:
            return False
        for ent in opponents:
            try:
                health: Health = world.component_for_entity(ent, Health)
            except KeyError:
                continue
            if health.current <= 0:
                return True
        return False

    def _count_active_witchfire(self, world: World) -> int:
        active_map: Dict[int, bool] = {ent: active.active for ent, active in world.get_component(ActiveSwitch)}
        total = 0
        for ent, tile_type in world.get_component(TileType):
            if tile_type.type_name == "witchfire" and active_map.get(ent, False):
                total += 1
        return total

    def _ability_cost_total(self, snapshot: OwnerSnapshot, ability_action: AbilityAction) -> int:
        snap = snapshot.ability_map.get(ability_action.ability_entity)
        if snap is None:
            return 0
        return sum(snap.cost.values())

    def _clone_bank_counts(self, world: World, owner_entity: int) -> Dict[str, int]:
        try:
            bank: TileBank = world.component_for_entity(owner_entity, TileBank)
        except KeyError:
            return {}
        return dict(bank.counts)

    def _compute_mana_deficits(
        self,
        counts: Dict[str, int],
        ability_map: Dict[int, AbilitySnapshot],
        clone_state: CloneState | None = None,
    ) -> Dict[str, int]:
        deficits: Dict[str, int] = {}
        for ability_entity, snap in ability_map.items():
            cooldown = snap.cooldown
            if clone_state is not None:
                clone_ability = clone_state.entity_map.get(ability_entity)
                if clone_ability is not None:
                    try:
                        cooldown_comp: AbilityCooldown = clone_state.world.component_for_entity(
                            clone_ability, AbilityCooldown
                        )
                        cooldown = cooldown_comp.remaining_turns
                    except KeyError:
                        cooldown = 0
            if cooldown > 0:
                continue
            for tile_type, required in snap.cost.items():
                missing = required - counts.get(tile_type, 0)
                if missing > 0:
                    deficits[tile_type] = deficits.get(tile_type, 0) + missing
        return deficits

    def _compute_bank_gains(
        self,
        baseline_counts: Dict[str, int],
        clone_counts: Dict[str, int],
        baseline_deficits: Dict[str, int],
    ) -> Tuple[int, int]:
        other_gain = 0
        secrets_gain = 0
        for tile_type, amount in clone_counts.items():
            previous = baseline_counts.get(tile_type, 0)
            delta = amount - previous
            if delta <= 0:
                continue
            if tile_type == "secrets":
                secrets_gain += delta
                continue
            if baseline_deficits.get(tile_type, 0) > 0:
                # Deficit reductions are already captured in needed_mana_delta.
                continue
            other_gain += delta
        return other_gain, secrets_gain

    def _count_new_affordable(
        self,
        clone_state: CloneState,
        clone_owner: int,
        snapshot: OwnerSnapshot,
        clone_counts: Dict[str, int],
    ) -> int:
        if not clone_counts:
            return 0
        new_affordable = 0
        for ability_entity, snap in snapshot.ability_map.items():
            if snap.cooldown > 0 or not snap.cost:
                continue
            was_affordable = snap.affordable
            clone_ability = clone_state.entity_map.get(ability_entity)
            if clone_ability is None:
                continue
            try:
                cooldown_comp: AbilityCooldown = clone_state.world.component_for_entity(
                    clone_ability, AbilityCooldown
                )
                if cooldown_comp.remaining_turns > 0:
                    continue
            except KeyError:
                pass
            can_afford_now = all(clone_counts.get(t, 0) >= n for t, n in snap.cost.items())
            if not was_affordable and can_afford_now:
                new_affordable += 1
        return new_affordable
