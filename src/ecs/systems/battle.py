"""
combat_model_v8.py

Battle Lines – Simultaneous Combat System (Additive Readiness Bonus)
--------------------------------------------------------------------
Key mechanics:
- Active men determine dice (tiered scaling by ratio).
- Manoeuvre affects accuracy.
- Combat skill affects damage.
- Armor reduces incoming damage and killed fraction.
- Battle readiness DIFFERENCE adds flat bonuses/penalties to manoeuvre and combat skill.
- Both sides fight simultaneously.
- Morale drops linearly with total casualties (20% = rout).
"""

from dataclasses import dataclass, asdict
import math
from typing import Dict, Optional, Tuple
import random

from esper import World

from ecs.components.regiment import Regiment
from ecs.components.army_roster import ArmyRoster
from ecs.components.active_turn import ActiveTurn
from ecs.events.bus import EventBus, EVENT_REGIMENT_CLICK, EVENT_BATTLE_RESOLVED


# ------------------------------------------------------------
# Utility
# ------------------------------------------------------------

def clamp(value: float, minimum: float, maximum: float) -> float:
    """Keep value within a specified range."""
    return max(minimum, min(value, maximum))



# ------------------------------------------------------------
# Combat tuning parameters
# ------------------------------------------------------------


@dataclass
class BattleConfig:
    base_morale_damage_per_hit: float = 3.0
    base_casualty_rate_per_hit: float = 0.10
    base_hit_chance_percent: float = 60.0
    hit_bonus_per_combat_skill_difference: float = 3.0
    hit_bonus_per_readiness_difference: float = 2.0
    base_frontline_size: float = 40.0
    minimum_readiness_to_attack: float = 5.0
    readiness_cost_per_attack: float = 5.0
    readiness_gain_when_defending: float = 2.0
    armour_morale_reduction_per_point: float = 0.06
    armour_casualty_reduction_per_point: float = 0.08
    dice_width: float = 1.0
    min_hit_chance_percent: float = 15.0
    max_hit_chance_percent: float = 80.0
    skill_damage_scale: float = 0.05
    armour_max_damage_reduction: float = 0.85
    morale_route_threshold: float = 0.4

    def derive_resolver_params(self) -> Dict[str, float]:
        return {
            "dice_width": self.dice_width,
            "readiness_manoeuvre_bonus": self.hit_bonus_per_readiness_difference * 0.05,
            "readiness_combat_bonus": self.hit_bonus_per_readiness_difference * 0.1,
            "base_hit_chance": self.base_hit_chance_percent,
            "hit_chance_scale": self.hit_bonus_per_combat_skill_difference,
            "min_hit_chance": self.min_hit_chance_percent,
            "max_hit_chance": self.max_hit_chance_percent,
            "min_damage": self.base_casualty_rate_per_hit * 0.25,
            "base_damage": self.base_casualty_rate_per_hit,
            "skill_damage_scale": self.skill_damage_scale,
            "armour_damage_modifier": self.armour_casualty_reduction_per_point,
            "armour_max_damage_reduction": self.armour_max_damage_reduction,
            "killed_fraction_base": self.base_morale_damage_per_hit * 0.02,
            "killed_fraction_armour_scale": self.armour_morale_reduction_per_point * 0.5,
            "base_morale": self.base_morale_damage_per_hit * 10,
            "morale_route_threshold": self.morale_route_threshold,
        }


# ------------------------------------------------------------
# Combat Resolver
# ------------------------------------------------------------

class CombatResolver:
    """Resolves simultaneous clashes between regiments with additive readiness bonuses."""

    def __init__(
        self,
        randomize: bool = False,
        random_seed: int = 42,
        config: Optional[BattleConfig] = None,
    ):
        self.randomize = randomize
        self.rng = random.Random(random_seed)
        self.config = config or BattleConfig()
        self._params = self.config.derive_resolver_params()

    # --------------------------------------------------------

    def _active_men(self, regiment: Regiment) -> int:
        """Effective number of soldiers able to fight."""
        return max(0, regiment.num_men - regiment.wounded_men - regiment.killed_men)

    # --------------------------------------------------------

    def _compute_dice_tiered(self, A: int, D: int) -> int:
        w = self._params["dice_width"]
        if D <= 0 or A <= 0:
            return max(0, A)
        r = A / D
        if r <= 1.0 + w:
            return A
        t = (r - (1.0 + w)) / w  # how many width-w tiers beyond base
        m = math.floor(t)
        alpha = t - m
        # Harmonic H_{m+1}
        H = sum(1.0/k for k in range(1, m+2))
        return math.floor((1.0 + w)*D + w*D*(H - 1.0) + alpha * (w*D) / (m + 2))

    # --------------------------------------------------------

    def _expected_hits(self, dice: float, hit_chance: float) -> float:
        """Compute expected or stochastic hits."""
        if not self.randomize:
            return dice * (hit_chance / 100.0)
        hits = 0
        for _ in range(int(dice)):
            if self.rng.random() < hit_chance / 100.0:
                hits += 1
        return hits

    def _split_to_dead_wounded(self, casualties: float, armor_rating: float) -> Tuple[int, int]:
        """Split casualties into killed and wounded based on the killed fraction."""
        params = self._params
        kill_ratio = clamp(
            params["killed_fraction_base"] - params["killed_fraction_armour_scale"] * armor_rating,
            0.0,
            1.0,
        )
        killed = max(0, int(round(casualties * kill_ratio)))
        wounded = max(0, int(round(casualties - killed)))
        return killed, wounded

    def _adjusted_stats(self, reg_a: Regiment, reg_b: Regiment) -> Tuple[float, float, float, float, float]:
        """Return readiness differential along with manoeuvre and combat-skill adjustments."""
        params = self._params
        br_diff = reg_a.battle_readiness - reg_b.battle_readiness
        manoeuvre_delta = params["readiness_manoeuvre_bonus"] * br_diff
        combat_delta = params["readiness_combat_bonus"] * br_diff
        mn_a = reg_a.manoeuvre + manoeuvre_delta
        mn_b = reg_b.manoeuvre - manoeuvre_delta
        cs_a = reg_a.combat_skill + combat_delta
        cs_b = reg_b.combat_skill - combat_delta
        return br_diff, mn_a, mn_b, cs_a, cs_b

    def _hit_chance(self, attacker_manoeuvre: float, defender_manoeuvre: float) -> float:
        params = self._params
        return clamp(
            params["base_hit_chance"] + (attacker_manoeuvre - defender_manoeuvre) * params["hit_chance_scale"],
            params["min_hit_chance"],
            params["max_hit_chance"],
        )

    def _damage_reduction(self, defender_armour: float) -> float:
        """Return fractional damage reduction provided by armour."""
        params = self._params
        if defender_armour <= 0:
            return 0.0
        if defender_armour <= 10:
            reduction = params["armour_damage_modifier"] * defender_armour
        else:
            reduction = 0.5 + (params["armour_max_damage_reduction"] - 0.5) * (1 - math.exp(-0.25 * (defender_armour - 10)))
        return clamp(reduction, 0.0, params["armour_max_damage_reduction"])

    def _damage(self, attacker_skill: float, defender_skill: float, defender_armour: float) -> float:
        params = self._params
        base = max(
            params["min_damage"],
            params["base_damage"] + params["skill_damage_scale"] * (attacker_skill - defender_skill),
        )
        reduction = self._damage_reduction(defender_armour)
        return base * max(0.0, 1.0 - reduction)
        

    
    # --------------------------------------------------------

    def resolve_clash(self, attacker: Regiment, defender: Regiment, *, attacking_side: str = "attacker") -> Dict:
        """Resolve a single-direction combat where ``attacker`` strikes ``defender``."""
        params = self._params

        active_attacker = self._active_men(attacker)
        active_defender = self._active_men(defender)

        br_diff, mn_attacker, mn_defender, cs_attacker, cs_defender = self._adjusted_stats(attacker, defender)

        dice = self._compute_dice_tiered(active_attacker, active_defender)
        hit_chance = self._hit_chance(mn_attacker, mn_defender)
        damage_per_hit = self._damage(cs_attacker, cs_defender, defender.armor_rating)

        hits = self._expected_hits(dice, hit_chance)
        casualties = hits * damage_per_hit

        killed, wounded = self._split_to_dead_wounded(casualties, defender.armor_rating)

        defender.killed_men += killed
        defender.wounded_men += wounded

        total_losses = killed + wounded
        loss_ratio = min(1.0, total_losses / max(defender.num_men, 1))
        morale_loss = (loss_ratio / params["morale_route_threshold"]) * params["base_morale"]
        defender.morale = max(0.0, defender.morale - morale_loss)

        summary = {
            "attacking_side": attacking_side,
            "readiness_difference": br_diff,
            "active_attacker": active_attacker,
            "active_defender": active_defender,
            "adjusted_manoeuvre_attacker": mn_attacker,
            "adjusted_manoeuvre_defender": mn_defender,
            "adjusted_combat_skill_attacker": cs_attacker,
            "adjusted_combat_skill_defender": cs_defender,
            "dice": dice,
            "hit_chance": hit_chance,
            "damage_per_hit": damage_per_hit,
            "hits": hits,
            "casualties_inflicted": casualties,
            "killed": killed,
            "wounded": wounded,
            "defender_total_losses": total_losses,
            "defender_loss_ratio": loss_ratio,
            "defender_morale_loss": morale_loss,
            "defender_morale_after": defender.morale,
            "defender_routed": defender.morale <= 0.0,
        }

        return {
            "attacker": asdict(attacker),
            "defender": asdict(defender),
            "combat_summary": summary,
        }


class BattleSystem:
    """Coordinates regiment clashes when players click their active units."""

    def __init__(
        self,
        world: World,
        event_bus: EventBus,
        *,
        config: Optional[BattleConfig] = None,
        randomize: bool = False,
        random_seed: int = 42,
    ):
        self.world = world
        self.event_bus = event_bus
        self.config = config or BattleConfig()
        self.resolver = CombatResolver(randomize=randomize, random_seed=random_seed, config=self.config)
        self.event_bus.subscribe(EVENT_REGIMENT_CLICK, self.on_regiment_click)

    def on_regiment_click(self, sender, **kwargs) -> None:
        owner_entity = kwargs.get("owner_entity")
        regiment_entity = kwargs.get("regiment_entity")
        if owner_entity is None or regiment_entity is None:
            return
        active_owner = self._active_owner()
        if active_owner is None or owner_entity != active_owner:
            return
        roster = self._roster_for_owner(owner_entity)
        if roster is None or not roster.regiment_entities:
            return
        if regiment_entity != roster.active_regiment():
            return
        opponent = self._select_opponent(owner_entity)
        if opponent is None:
            return
        opponent_owner, opponent_roster = opponent
        defender_entity = opponent_roster.active_regiment()
        try:
            attacker_regiment = self.world.component_for_entity(regiment_entity, Regiment)
            defender_regiment = self.world.component_for_entity(defender_entity, Regiment)
        except KeyError:
            return

        if attacker_regiment.battle_readiness < self.config.minimum_readiness_to_attack:
            return

        forward = self.resolver.resolve_clash(attacker_regiment, defender_regiment, attacking_side="attacker")
        counter = self.resolver.resolve_clash(defender_regiment, attacker_regiment, attacking_side="defender")

        cost = int(self.config.readiness_cost_per_attack)
        if cost > 0:
            attacker_regiment.battle_readiness = max(0, attacker_regiment.battle_readiness - cost)
            defender_regiment.battle_readiness = max(0, defender_regiment.battle_readiness - cost)

        self.event_bus.emit(
            EVENT_BATTLE_RESOLVED,
            attacker_owner=owner_entity,
            defender_owner=opponent_owner,
            attacker_regiment=regiment_entity,
            defender_regiment=defender_entity,
            forward=forward,
            counter=counter,
        )

    def _active_owner(self) -> Optional[int]:
        entries = list(self.world.get_component(ActiveTurn))
        if not entries:
            return None
        return entries[0][1].owner_entity

    def _roster_for_owner(self, owner_entity: int) -> Optional[ArmyRoster]:
        try:
            return self.world.component_for_entity(owner_entity, ArmyRoster)
        except KeyError:
            return None

    def _select_opponent(self, owner_entity: int) -> Optional[Tuple[int, ArmyRoster]]:
        for other_owner, roster in self.world.get_component(ArmyRoster):
            if other_owner == owner_entity:
                continue
            if roster.regiment_entities:
                return other_owner, roster
        return None


