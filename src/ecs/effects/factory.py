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
