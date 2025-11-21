from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Mapping


def sanitize_affinity_values(data: Mapping[str, Any] | Iterable[tuple[str, Any]] | None) -> Dict[str, float]:
    """Return a cleaned copy of affinity data with numeric entries as floats."""

    results: Dict[str, float] = {}
    if data is None:
        return results
    if isinstance(data, Mapping):
        items = data.items()
    else:
        items = data
    for key, value in items:
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric == 0:
            continue
        if not isinstance(key, str):
            try:
                key = str(key)
            except Exception:
                continue
        results[key] = numeric
    return results


def combine_affinity_maps(*maps: Mapping[str, Any] | Iterable[tuple[str, Any]] | None) -> Dict[str, float]:
    """Merge multiple affinity mappings into a single dictionary."""

    combined: Dict[str, float] = {}
    for mapping in maps:
        sanitized = sanitize_affinity_values(mapping)
        for key, amount in sanitized.items():
            combined[key] = combined.get(key, 0.0) + amount
    return combined


def normalize_affinity_map(mapping: Mapping[str, Any] | Iterable[tuple[str, Any]] | None) -> Dict[str, float]:
    """Return a unit-length vector representation of the affinity map."""

    sanitized = sanitize_affinity_values(mapping)
    if not sanitized:
        return {}
    norm = math.sqrt(sum(amount * amount for amount in sanitized.values()))
    if norm <= 0:
        return {}
    return {key: amount / norm for key, amount in sanitized.items()}


def affinity_distance(vector_a: Mapping[str, float], vector_b: Mapping[str, float]) -> float:
    """Compute the Euclidean distance between two affinity vectors."""

    keys = set(vector_a.keys()) | set(vector_b.keys())
    if not keys:
        return 0.0
    total = 0.0
    for key in keys:
        diff = vector_a.get(key, 0.0) - vector_b.get(key, 0.0)
        total += diff * diff
    return math.sqrt(total)
