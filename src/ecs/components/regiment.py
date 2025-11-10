from dataclasses import dataclass

@dataclass
class Regiment:
    """Represents a fighting unit on the battlefield.

    Fields:
        name: Display name for the regiment.
    unit_type: One of "infantry", "cavalry", "ranged".
        num_men: Current number of soldiers available for action (fit for duty).
        combat_skill: Accuracy / lethality modifier (baseline 1.0 typical ~ average troops).
        armor_rating: Mitigates incoming casualty + morale effects (0-1 suggested range or arbitrary scaling).
        manoeuvre: Determines how many men can effectively engage (frontage / deployment agility).
        morale: Current morale points (acts like HP for routing). 0 => routing.
        max_morale: Maximum morale ceiling for recovery / initialization.
        battle_readiness: Accumulated readiness derived from tile control or pre-battle prep.
    wounded_men: Temporarily disabled (can potentially return after battle or via effects).
    killed_men: Permanently lost soldiers.
    """
    owner_id: int  # entity id of owning player/agent
    name: str
    unit_type: str  # "infantry", "cavalry", "ranged"
    num_men: int
    combat_skill: float
    armor_rating: float
    manoeuvre: float
    morale: float = 100.0
    max_morale: float = 100.0
    battle_readiness: int = 0
    wounded_men: int = 0
    killed_men: int = 0
