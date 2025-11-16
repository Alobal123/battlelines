from __future__ import annotations

import random
from typing import Dict

from ecs.components.tile_bank import TileBank


def drain_bank_counts(
    bank: TileBank,
    amount: int,
    metadata: dict[str, object] | None = None,
    *,
    rng: random.Random | None = None,
) -> Dict[str, int]:
    """Drain mana from a bank according to the provided mode.

    Supported modes mirror those used by deplete and mana_drain effects:
      - "type" / "specific": drain a single named type (``metadata['type_name']``).
      - "all": drain up to ``amount`` from every type with a positive count.
      - "random_eligible": choose a random type that has at least ``amount`` available.

    Returns a mapping of type -> amount drained and mutates ``bank.counts`` in place.
    """

    if amount <= 0:
        return {}
    if metadata is None:
        metadata = {}
    mode = str(metadata.get("mode", "type")).lower()

    if mode in {"type", "specific"}:
        type_name_obj = metadata.get("type_name")
        if not isinstance(type_name_obj, str) or not type_name_obj:
            return {}
        current = bank.counts.get(type_name_obj, 0)
        if current <= 0:
            return {}
        removed = min(amount, current)
        bank.counts[type_name_obj] = current - removed
        return {type_name_obj: removed}

    if mode == "all":
        deltas: Dict[str, int] = {}
        for type_name, current in list(bank.counts.items()):
            if current <= 0:
                continue
            removed = min(amount, current)
            if removed <= 0:
                continue
            bank.counts[type_name] = current - removed
            deltas[type_name] = removed
        return deltas

    if mode == "random_eligible":
        rng = rng or random
        eligible = [name for name, value in bank.counts.items() if value >= amount]
        if not eligible:
            return {}
        type_name = rng.choice(eligible)
        removed = min(amount, bank.counts.get(type_name, 0))
        if removed <= 0:
            return {}
        bank.counts[type_name] -= removed
        return {type_name: removed}

    return {}