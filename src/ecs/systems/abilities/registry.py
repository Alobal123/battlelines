from __future__ import annotations

from importlib import metadata
from typing import Dict, Iterable

from ecs.systems.abilities.base import AbilityResolver
from ecs.systems.abilities.crimson_pulse import CrimsonPulseResolver
from ecs.systems.abilities.tactical_shift import TacticalShiftResolver

_PLUGIN_GROUP = "battlelines.ability_resolvers"
_plugin_loaded = False
_registry: Dict[str, AbilityResolver] = {}


def register_resolver(resolver: AbilityResolver) -> None:
    """Register a resolver provided by external content."""

    _registry[resolver.name] = resolver


def register_resolvers(resolvers: Iterable[AbilityResolver]) -> None:
    for resolver in resolvers:
        register_resolver(resolver)


def _load_entry_point_resolvers() -> None:
    global _plugin_loaded
    if _plugin_loaded:
        return
    try:
        entry_points = metadata.entry_points()
    except Exception:
        _plugin_loaded = True
        return
    if hasattr(entry_points, "select"):
        candidates = entry_points.select(group=_PLUGIN_GROUP)
    else:  # pragma: no cover - legacy importlib.metadata API
        candidates = entry_points.get(_PLUGIN_GROUP, [])
    for entry_point in candidates:
        try:
            loaded = entry_point.load()
        except Exception:
            continue
        _register_from_object(loaded)
    _plugin_loaded = True


def _register_from_object(obj):
    if obj is None:
        return
    if hasattr(obj, "resolve") and hasattr(obj, "name"):
        register_resolver(obj)  # type: ignore[arg-type]
        return
    if callable(obj):
        try:
            produced = obj()
        except Exception:
            return
        _register_from_object(produced)
        return
    if isinstance(obj, dict):
        for value in obj.values():
            _register_from_object(value)
        return
    if isinstance(obj, (list, tuple, set, frozenset)):
        for item in obj:
            _register_from_object(item)
        return


def _builtin_resolvers() -> Dict[str, AbilityResolver]:
    return {
        TacticalShiftResolver.name: TacticalShiftResolver(),
        CrimsonPulseResolver.name: CrimsonPulseResolver(),
    }


def create_resolver_registry(overrides: Dict[str, AbilityResolver] | None = None) -> Dict[str, AbilityResolver]:
    """Combine built-in, plugin, and override resolvers into a single map."""

    _load_entry_point_resolvers()
    combined: Dict[str, AbilityResolver] = _builtin_resolvers()
    combined.update(_registry)
    if overrides:
        combined.update(overrides)
    return combined


__all__ = [
    "create_resolver_registry",
    "register_resolver",
    "register_resolvers",
]
