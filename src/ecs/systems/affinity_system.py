from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, Mapping, cast

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.affinity import Affinity
from ecs.components.skill import Skill
from ecs.components.skill_list_owner import SkillListOwner
from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_CHOICE_GRANTED,
    EVENT_AFFINITY_UPDATED,
    EVENT_SKILL_CHOICE_GRANTED,
    EVENT_TICK,
)


class AffinitySystem:
    """Aggregates affinity totals from base alignments, abilities, and skills."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self._dirty_entities: set[int] = set()
        setattr(world, "affinity_system", self)
        self.event_bus.subscribe(EVENT_TICK, self._on_tick)
        self.event_bus.subscribe(EVENT_ABILITY_CHOICE_GRANTED, self._on_affinity_source_changed)
        self.event_bus.subscribe(EVENT_SKILL_CHOICE_GRANTED, self._on_affinity_source_changed)
        # Rebuild initial state for any pre-seeded affinity components.
        self.recalculate_all()

    # Public API ---------------------------------------------------------
    def mark_dirty(self, entity: int) -> None:
        if entity is None:
            return
        if not isinstance(entity, int):
            try:
                entity = int(entity)
            except (TypeError, ValueError):
                return
        if entity < 0:
            return
        self._dirty_entities.add(entity)

    def recalculate_entity(self, entity: int) -> None:
        self.mark_dirty(entity)
        self._flush_dirty()

    def recalculate_all(self) -> None:
        self._dirty_entities.update(ent for ent, _ in self.world.get_component(Affinity))
        self._flush_dirty()

    # Event handlers -----------------------------------------------------
    def _on_tick(self, sender, **kwargs) -> None:
        if not self._dirty_entities:
            return
        self._flush_dirty()

    def _on_affinity_source_changed(self, sender, **payload) -> None:
        owner_entity = payload.get("owner_entity")
        if owner_entity is None:
            return
        self.recalculate_entity(int(owner_entity))

    # Internal helpers ---------------------------------------------------
    def _flush_dirty(self) -> None:
        if not self._dirty_entities:
            return
        dirty = sorted(self._dirty_entities)
        self._dirty_entities.clear()
        for entity in dirty:
            self._recalculate_entity(entity)

    def _recalculate_entity(self, entity: int) -> None:
        try:
            affinity = self.world.component_for_entity(entity, Affinity)
        except KeyError:
            return

        previous_totals = dict(affinity.totals)
        previous_contributions = {
            key: dict(values)
            for key, values in affinity.contributions.items()
        }
        previous_breakdown = [dict(entry) for entry in affinity.breakdown]

        totals: Dict[str, int] = defaultdict(int)
        contributions: Dict[str, Dict[str, int]] = {
            "base": {},
            "abilities": {},
            "skills": {},
        }
        breakdown: list[dict[str, object]] = []

        base_values = self._sanitize_map(affinity.base)
        if base_values:
            contributions["base"] = dict(base_values)
            breakdown.append({
                "source": "base",
                "label": "Base Alignment",
                "values": dict(base_values),
            })
            for tile, amount in base_values.items():
                totals[tile] += amount

        ability_totals, ability_breakdown = self._collect_ability_contributions(entity)
        if ability_totals:
            contributions["abilities"] = dict(ability_totals)
            breakdown.extend(ability_breakdown)
            for tile, amount in ability_totals.items():
                totals[tile] += amount

        skill_totals, skill_breakdown = self._collect_skill_contributions(entity)
        if skill_totals:
            contributions["skills"] = dict(skill_totals)
            breakdown.extend(skill_breakdown)
            for tile, amount in skill_totals.items():
                totals[tile] += amount

        sorted_totals = dict(sorted(totals.items()))
        normalized_contributions = {
            key: dict(sorted(values.items()))
            for key, values in contributions.items()
        }
        normalized_breakdown: list[dict[str, object]] = []
        for entry in breakdown:
            if not isinstance(entry, dict):
                continue
            raw_values = cast(Mapping[str, Any] | None, entry.get("values"))
            sanitized = self._sanitize_map(raw_values)
            normalized_breakdown.append({
                "source": entry.get("source"),
                "label": entry.get("label"),
                "values": dict(sorted(sanitized.items())),
            })

        changed = (
            previous_totals != sorted_totals
            or previous_contributions != normalized_contributions
            or previous_breakdown != normalized_breakdown
        )

        affinity.totals = sorted_totals
        affinity.contributions = normalized_contributions
        affinity.breakdown = normalized_breakdown

        if changed:
            self.event_bus.emit(
                EVENT_AFFINITY_UPDATED,
                owner_entity=entity,
                totals=sorted_totals,
                contributions=normalized_contributions,
                breakdown=normalized_breakdown,
            )

    def _collect_ability_contributions(self, owner_entity: int) -> tuple[Dict[str, int], list[dict[str, object]]]:
        try:
            owner = self.world.component_for_entity(owner_entity, AbilityListOwner)
        except KeyError:
            return {}, []
        totals: Dict[str, int] = defaultdict(int)
        breakdown: list[dict[str, object]] = []
        for ability_entity in list(owner.ability_entities):
            ability = self._safe_component(ability_entity, Ability)
            if ability is None:
                continue
            cost_map = self._sanitize_map(getattr(ability, "cost", {}))
            bonus_map = self._sanitize_map(getattr(ability, "affinity_bonus", {}))
            combined = dict(cost_map)
            for tile, amount in bonus_map.items():
                combined[tile] = combined.get(tile, 0) + amount
            if not combined:
                continue
            label = ability.name or f"ability:{ability_entity}"
            breakdown.append({
                "source": "ability",
                "label": label,
                "values": combined,
            })
            for tile, amount in combined.items():
                totals[tile] += amount
        return dict(totals), breakdown

    def _collect_skill_contributions(self, owner_entity: int) -> tuple[Dict[str, int], list[dict[str, object]]]:
        try:
            owner = self.world.component_for_entity(owner_entity, SkillListOwner)
        except KeyError:
            return {}, []
        totals: Dict[str, int] = defaultdict(int)
        breakdown: list[dict[str, object]] = []
        for skill_entity in list(owner.skill_entities):
            skill = self._safe_component(skill_entity, Skill)
            if skill is None:
                continue
            bonus_map = self._sanitize_map(getattr(skill, "affinity_bonus", {}))
            if not bonus_map:
                continue
            label = skill.name or f"skill:{skill_entity}"
            breakdown.append({
                "source": "skill",
                "label": label,
                "values": dict(bonus_map),
            })
            for tile, amount in bonus_map.items():
                totals[tile] += amount
        return dict(totals), breakdown

    @staticmethod
    def _sanitize_map(
        raw_map: Mapping[str, Any] | Iterable[tuple[str, Any]] | None,
    ) -> Dict[str, int]:
        result: Dict[str, int] = {}
        if raw_map is None:
            return result
        if isinstance(raw_map, Mapping):
            items = raw_map.items()
        else:
            items = raw_map
        for key, value in items:
            try:
                amount = int(value)
            except (TypeError, ValueError):
                continue
            if amount == 0:
                continue
            if not isinstance(key, str):
                try:
                    key = str(key)
                except Exception:
                    continue
            result[key] = amount
        return result

    def _safe_component(self, entity: int, component_type):
        try:
            return self.world.component_for_entity(entity, component_type)
        except KeyError:
            return None
