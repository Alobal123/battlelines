from dataclasses import dataclass, field


@dataclass(slots=True)
class EffectList:
    """Holds references to effect entities that currently influence an owner."""

    effect_entities: list[int] = field(default_factory=list)
