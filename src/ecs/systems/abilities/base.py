from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from esper import World

from ecs.components.ability import Ability
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects
from ecs.events.bus import EventBus, EVENT_EFFECT_APPLY


@dataclass(slots=True)
class AbilityContext:
    """Execution context shared by ability resolvers."""

    world: World
    event_bus: EventBus
    ability_entity: int
    ability: Ability
    pending: PendingAbilityTarget
    owner_entity: int | None
    active_owner: int | None
    scratchpad: dict[str, Any] = field(default_factory=dict)


class AbilityResolver(Protocol):
    """Interface implemented by concrete ability resolvers."""

    name: str

    def resolve(self, ctx: AbilityContext) -> None:
        ...


class EffectDrivenAbilityResolver:
    """Mixin providing helpers for abilities defined via AbilityEffects."""

    def _apply_declared_effects(self, ctx: AbilityContext) -> list[int]:
        specs = self._collect_effect_specs(ctx)
        if not specs:
            return []
        affected: list[int] = []
        for spec in specs:
            target = self._select_effect_target(ctx, spec)
            if target is None:
                continue
            metadata = self._build_effect_metadata(ctx, spec)
            payload: dict[str, Any] = {
                "owner_entity": target,
                "source_entity": ctx.ability_entity,
                "slug": spec.slug,
                "metadata": metadata,
            }
            if spec.turns is not None:
                payload["turns"] = spec.turns
            ctx.event_bus.emit(EVENT_EFFECT_APPLY, **payload)
            affected.append(target)
        # Deduplicate while preserving order
        unique: list[int] = []
        seen: set[int] = set()
        for entity in affected:
            if entity is None:
                continue
            if entity in seen:
                continue
            seen.add(entity)
            unique.append(entity)
        return unique

    def _collect_effect_specs(self, ctx: AbilityContext) -> tuple[AbilityEffectSpec, ...]:
        try:
            component = ctx.world.component_for_entity(ctx.ability_entity, AbilityEffects)
        except KeyError:
            return ()
        return component.effects

    def _select_effect_target(self, ctx: AbilityContext, spec: AbilityEffectSpec) -> int | None:
        match spec.target:
            case "self":
                return ctx.owner_entity
            case "opponent":
                return self._find_opponent_entity(ctx)
            case "pending_target":
                return ctx.pending.target_entity
            case "pending_target_or_self":
                return ctx.pending.target_entity or ctx.owner_entity
            case "board":
                return self._find_board_entity(ctx)
            case _:
                return None

    def _build_effect_metadata(self, ctx: AbilityContext, spec: AbilityEffectSpec) -> dict[str, Any]:
        metadata = dict(spec.metadata)
        params = ctx.ability.params if isinstance(ctx.ability.params, dict) else {}
        for key, param_key in spec.param_overrides.items():
            if isinstance(params, dict) and param_key in params:
                metadata[key] = params[param_key]
        if ctx.owner_entity is not None:
            metadata.setdefault("source_owner", ctx.owner_entity)
        if ctx.pending.row is not None:
            metadata.setdefault("origin_row", ctx.pending.row)
        if ctx.pending.col is not None:
            metadata.setdefault("origin_col", ctx.pending.col)
        context_reads = metadata.pop("context_read", None)
        metadata["_ability_context"] = ctx.scratchpad
        if isinstance(context_reads, dict):
            for target_key, ctx_key in context_reads.items():
                if not isinstance(target_key, str) or not isinstance(ctx_key, str):
                    continue
                default_value = metadata.get(target_key, 0)
                metadata[target_key] = ctx.scratchpad.get(ctx_key, default_value)
        metadata.setdefault("reason", spec.slug)
        return metadata

    def _find_opponent_entity(self, ctx: AbilityContext) -> int | None:
        if ctx.owner_entity is None:
            return None
        from ecs.components.ability_list_owner import AbilityListOwner

        for entity, _ in ctx.world.get_component(AbilityListOwner):
            if entity != ctx.owner_entity:
                return entity
        return None

    def _find_board_entity(self, ctx: AbilityContext) -> int | None:
        from ecs.components.board import Board

        boards = list(ctx.world.get_component(Board))
        if not boards:
            return None
        return boards[0][0]
