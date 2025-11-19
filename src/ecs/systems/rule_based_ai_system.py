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
from ecs.components.forbidden_knowledge import ForbiddenKnowledge


# ---------------------------------------------------------------------------
# Scoring weights (tuned heuristics)
# ---------------------------------------------------------------------------
KILL_BONUS = 1_000_000_000
WITCHFIRE_BONUS = 1_000_000
CHAOS_TILE_BONUS = 5_000_000
EXTRA_TURN_BONUS = 100_000_000
ABILITY_USAGE_BONUS = 100_000
FREE_ACTION_BONUS = 500_000
ABILITY_COST_WEIGHT = 10_000
NEW_AFFORDABLE_WEIGHT = 1_000
NEEDED_MANA_WEIGHT = 100
MANA_GAIN_WEIGHT = 10
SECRETS_GAIN_WEIGHT = 1
KNOWLEDGE_COMPLETION_BONUS = 3_000_000
RANDOM_TIE_BREAKER = 0.001
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
        base_chaos = self._count_active_type(self.world, "chaos")
        post_chaos = self._count_active_type(clone_world, "chaos")
        witchfire_cleared = max(0, base_witchfire - post_witchfire)
        chaos_cleared = max(0, base_chaos - post_chaos)
        kill_flag = 1 if self._any_opponent_defeated(clone_world, owner_entity) else 0
        ability_usage_flag = 1 if candidate[0] == "ability" else 0
        ability_cost_total = 0
        free_action_bonus = 0
        extra_turn_bonus = 0
        if candidate[0] == "ability":
            ability_action = cast(AbilityAction, candidate[1])
            ability_cost_total = self._ability_cost_total(snapshot, ability_action)
            ability_snapshot = snapshot.ability_map.get(ability_action.ability_entity)
            if ability_snapshot is not None and not ability_snapshot.ends_turn:
                free_action_bonus = FREE_ACTION_BONUS
        if candidate[0] == "swap" and clone_state.engine.last_action_generated_extra_turn:
            extra_turn_bonus = EXTRA_TURN_BONUS
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
        knowledge_completion_bonus = 0
        meter_state = self._current_forbidden_knowledge()
        if meter_state is not None:
            current_value, max_value = meter_state
            remaining = max(0, max_value - current_value)
            if remaining > 0 and secrets_gain >= remaining:
                knowledge_completion_bonus = KNOWLEDGE_COMPLETION_BONUS
        score = (
            kill_flag * KILL_BONUS
            + witchfire_cleared * WITCHFIRE_BONUS
            + chaos_cleared * CHAOS_TILE_BONUS
            + extra_turn_bonus
            + ability_usage_flag * ABILITY_USAGE_BONUS
            + free_action_bonus
            + ability_cost_total * ABILITY_COST_WEIGHT
            + new_affordable * NEW_AFFORDABLE_WEIGHT
            + needed_mana_delta * NEEDED_MANA_WEIGHT
            + other_mana_gain * MANA_GAIN_WEIGHT
            + secrets_gain * SECRETS_GAIN_WEIGHT
            + knowledge_completion_bonus
            + self.random.random() * RANDOM_TIE_BREAKER
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
        return self._count_active_type(world, "witchfire")

    def _count_active_type(self, world: World, type_name: str) -> int:
        active_map: Dict[int, bool] = {ent: active.active for ent, active in world.get_component(ActiveSwitch)}
        total = 0
        for ent, tile_type in world.get_component(TileType):
            if tile_type.type_name == type_name and active_map.get(ent, False):
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

    def _current_forbidden_knowledge(self) -> Tuple[int, int] | None:
        entries = list(self.world.get_component(ForbiddenKnowledge))
        if not entries:
            return None
        meter = entries[0][1]
        return meter.value, meter.max_value

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
