from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping


@dataclass(frozen=True, slots=True)
class EffectDefinition:
    """Static description for an effect type.

    The definition describes how an effect should be instantiated and provides
    metadata that systems can inspect when resolving gameplay interactions.
    """

    slug: str
    display_name: str
    description: str = ""
    tags: tuple[str, ...] = ()
    default_metadata: Mapping[str, object] = field(default_factory=dict)


class EffectRegistry:
    """In-memory collection of effect definitions."""

    def __init__(self) -> None:
        self._definitions: dict[str, EffectDefinition] = {}

    def register(self, definition: EffectDefinition) -> None:
        if definition.slug in self._definitions:
            raise ValueError(f"Effect '{definition.slug}' already registered")
        self._definitions[definition.slug] = definition

    def get(self, slug: str) -> EffectDefinition:
        try:
            return self._definitions[slug]
        except KeyError as exc:
            raise KeyError(f"Effect '{slug}' is not registered") from exc

    def has(self, slug: str) -> bool:
        return slug in self._definitions

    def all(self) -> Iterable[EffectDefinition]:
        return tuple(self._definitions.values())


default_effect_registry = EffectRegistry()


def register_effect(definition: EffectDefinition) -> None:
    default_effect_registry.register(definition)
