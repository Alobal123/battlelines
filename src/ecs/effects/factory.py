from __future__ import annotations

from ecs.effects.registry import EffectDefinition, default_effect_registry, register_effect


def ensure_default_effects_registered() -> None:
    """Register core effect definitions if they are not already present."""

    def _register(definition: EffectDefinition) -> None:
        if default_effect_registry.has(definition.slug):
            return
        register_effect(definition)

    _register(
        EffectDefinition(
            slug="damage",
            display_name="Damage",
            description="Applies damage when triggered.",
            default_metadata={
                "amount": 0,
                "reason": "effect",
                "source_owner": None,
                "turns": 0,
            },
        )
    )
    _register(
        EffectDefinition(
            slug="heal",
            display_name="Heal",
            description="Applies healing when triggered.",
            default_metadata={
                "amount": 0,
                "reason": "effect",
                "source_owner": None,
                "turns": 0,
            },
        )
    )
    _register(
        EffectDefinition(
            slug="board_clear_area",
            display_name="Clear Tiles",
            description="Removes tiles in an area, triggering cascades.",
            default_metadata={
                "shape": "square",
                "radius": 0,
                "reason": "effect",
            },
        )
    )
    _register(
        EffectDefinition(
            slug="board_transform_type",
            display_name="Transform Tiles",
            description="Converts tiles of a given type to another type.",
            default_metadata={
                "target_type": "",
                "reason": "effect",
            },
        )
    )
    _register(
        EffectDefinition(
            slug="damage_bonus",
            display_name="Damage Bonus",
            description="Increases damage dealt by the owner.",
            default_metadata={
                "bonus": 1,
                "reason": "damage_bonus",
                "stack_key": "damage_bonus",
            },
        )
    )
    _register(
        EffectDefinition(
            slug="deplete",
            display_name="Deplete",
            description="Removes mana from the target's tile bank.",
            default_metadata={
                "amount": 0,
                "mode": "type",
                "type_name": "",
                "reason": "effect",
                "source_owner": None,
            },
        )
    )
    _register(
        EffectDefinition(
            slug="mana_drain",
            display_name="Mana Drain",
            description="Drains mana of a specific amount from the target.",
            default_metadata={
                "amount": 0,
                "mode": "random_eligible",
                "reason": "mana_drain",
                "source_owner": None,
            },
        )
    )
    _register(
        EffectDefinition(
            slug="frailty",
            display_name="Frailty",
            description="Increases damage taken by the affected entity.",
            default_metadata={
                "bonus": 1,
                "reason": "frailty",
            },
        )
    )
    _register(
        EffectDefinition(
            slug="poison",
            display_name="Poison",
            description="Loses health at the start of each of its turns.",
            default_metadata={
                "amount": 1,
                "reason": "poison",
                "turns": 0,
                "stacks": True,
                "stack_key": "poison",
            },
        )
    )
    _register(
        EffectDefinition(
            slug="thorns",
            display_name="Thorns",
            description="Reflects damage back to attackers when struck by abilities or witchfire.",
            default_metadata={
                "amount": 1,
                "reason": "thorns",
                "turns": 0,
                "stacks": False,
                "stack_key": "thorns",
            },
        )
    )
    _register(
        EffectDefinition(
            slug="tile_sacrifice",
            display_name="Tile Sacrifice",
            description="Removes a tile without refilling and grants rewards.",
            default_metadata={
                "multiplier": 3,
                "reason": "tile_sacrifice",
                "refill": False,
            },
        )
    )
    _register(
        EffectDefinition(
            slug="self_reprimand",
            display_name="Self Reprimand",
            description="When the owner damages themselves, retaliate and gain blood mana.",
            default_metadata={
                "bonus_damage": 1,
                "mana_amount": 1,
                "mana_type": "blood",
                "reason": "self_reprimand",
            },
        )
    )
    _register(
        EffectDefinition(
            slug="void_tithe",
            display_name="Void Tithe",
            description="At the end of the owner's turn, deal damage equal to empty board tiles.",
            default_metadata={
                "multiplier": 1,
                "reason": "void_tithe",
            },
        )
    )
    _register(
        EffectDefinition(
            slug="blood_covenant",
            display_name="Blood Covenant",
            description="At the start of the owner's turn, both battlers lose health.",
            default_metadata={
                "amount": 1,
                "reason": "blood_covenant",
            },
        )
    )
    _register(
        EffectDefinition(
            slug="locked_scent",
            display_name="Locked Scent",
            description="A lingering scent marker with no direct effect.",
            default_metadata={
                "stacks": True,
                "stack_key": "locked_scent",
            },
        )
    )
    _register(
        EffectDefinition(
            slug="tile_guarded",
            display_name="Guarded Tile",
            description="Deals damage to opponents who disturb the tile.",
            default_metadata={
                "damage": 1,
                "reason": "guarded_tile",
                "source_owner": None,
                "overlay_icon": "tile_guarded",
                "overlay_tint": (224, 196, 64),
            },
        )
    )
