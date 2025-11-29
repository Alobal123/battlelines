from __future__ import annotations

from collections.abc import Callable
from typing import Any, Dict, Iterable, List, Tuple, cast

from esper import World

from ecs.components.effect import Effect
from ecs.components.effect_duration import EffectDuration
from ecs.components.effect_expiry import EffectExpireOnEvents
from ecs.components.effect_list import EffectList
from ecs.effects.registry import default_effect_registry, EffectDefinition
from ecs.events.bus import (
    EVENT_EFFECT_APPLY,
    EVENT_EFFECT_APPLIED,
    EVENT_EFFECT_EXPIRED,
    EVENT_EFFECT_REFRESHED,
    EVENT_EFFECT_REMOVE,
    EVENT_TURN_ADVANCED,
    EventBus,
)


class EffectLifecycleSystem:
    """Handles creation, refreshing, and expiration of effect entities."""

    def __init__(self, world: World, event_bus: EventBus):
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_EFFECT_APPLY, self.on_effect_apply)
        self.event_bus.subscribe(EVENT_EFFECT_REMOVE, self.on_effect_remove)
        self.event_bus.subscribe(EVENT_TURN_ADVANCED, self.on_turn_advanced)
        self._event_handlers: Dict[str, Callable] = {}
        self._event_triggers: Dict[str, List[Tuple[int, bool, str]]] = {}

    def on_effect_apply(self, sender, **kwargs):
        slug = kwargs.get("slug")
        owner_entity = kwargs.get("owner_entity")
        if slug is None or owner_entity is None:
            return
        source_entity = kwargs.get("source_entity")
        metadata_override: Dict[str, Any] = dict(kwargs.get("metadata") or {})
        definition = self._get_definition(slug)
        metadata = self._merge_metadata(definition, metadata_override)
        turns = kwargs.get("turns")
        if turns is None:
            turns = metadata.get("turns")
        allow_multiple = kwargs.get("allow_multiple")
        metadata_allow_multiple = metadata.pop("allow_multiple", None)
        if allow_multiple is None:
            if metadata_allow_multiple is not None:
                allow_multiple = metadata_allow_multiple
            else:
                allow_multiple = True
        allow_multiple = bool(allow_multiple)
        cumulative = bool(kwargs.get("cumulative", metadata.pop("cumulative", False)))
        if definition is not None and "cumulative" in definition.tags:
            cumulative = True
        count_delta = kwargs.get("count")
        if count_delta is None:
            count_delta = metadata.pop("count", None)
        if count_delta is None:
            count_delta = 0
        try:
            count_delta = int(count_delta)
        except (TypeError, ValueError):
            count_delta = 0
        if count_delta < 0:
            count_delta = 0
        stack_key = kwargs.get("stack_key", metadata.pop("stack_key", None))
        refresh_existing = bool(kwargs.get("refresh", False))
        expire_on_events = kwargs.get("expire_on_events")
        if expire_on_events is None:
            expire_on_events = metadata.pop("expire_on_events", ())
        expire_on_events = tuple(expire_on_events) if expire_on_events else ()
        expire_match_owner = bool(kwargs.get("expire_match_owner", metadata.pop("expire_match_owner", False)))
        payload_owner_key = kwargs.get(
            "expire_payload_owner_key",
            metadata.pop("expire_payload_owner_key", "owner_entity"),
        )
        effect_list = self._ensure_effect_list(owner_entity)
        duplicates = self._find_effects(effect_list, slug, stack_key)
        if duplicates and cumulative:
            target_entity = duplicates[0]
            self._accumulate_effect(
                target_entity,
                count_delta,
                metadata,
                source_entity,
            )
            return
        if duplicates and refresh_existing:
            for effect_entity in duplicates:
                self._refresh_effect(
                    effect_entity,
                    metadata,
                    turns,
                    allow_multiple,
                    cumulative,
                    count_delta,
                    stack_key,
                    source_entity,
                    expire_on_events,
                    expire_match_owner,
                    payload_owner_key,
                )
            return
        if duplicates and not allow_multiple:
            for effect_entity in list(duplicates):
                self._expire_effect(effect_entity, reason="replaced")
        components: list[Any] = [
            Effect(
                slug=slug,
                owner_entity=owner_entity,
                source_entity=source_entity,
                allow_multiple=allow_multiple,
                stack_key=stack_key,
                cumulative=cumulative,
                count=max(0, count_delta),
                metadata=metadata,
            )
        ]
        if turns is not None:
            try:
                remaining_turns = int(turns)
            except (TypeError, ValueError):
                remaining_turns = 0
            components.append(EffectDuration(remaining_turns=max(0, remaining_turns)))
        if expire_on_events:
            components.append(
                EffectExpireOnEvents(
                    events=tuple(expire_on_events),
                    match_owner=expire_match_owner,
                    payload_owner_key=payload_owner_key,
                )
            )
        effect_entity = self.world.create_entity(*components)
        effect_list.effect_entities.append(effect_entity)
        if expire_on_events:
            self._register_event_triggers(
                effect_entity,
                tuple(expire_on_events),
                expire_match_owner,
                payload_owner_key,
            )
        try:
            self.world.component_for_entity(effect_entity, Effect)
        except KeyError:
            pass
        self.event_bus.emit(
            EVENT_EFFECT_APPLIED,
            effect_entity=effect_entity,
            owner_entity=owner_entity,
            slug=slug,
        )

    def on_effect_remove(self, sender, **kwargs):
        effect_entity = kwargs.get("effect_entity")
        reason = kwargs.get("reason", "removed")
        if effect_entity is not None:
            self._expire_effect(effect_entity, reason=reason)
            return
        owner_entity = kwargs.get("owner_entity")
        if owner_entity is None:
            return
        slug = kwargs.get("slug")
        stack_key = kwargs.get("stack_key")
        remove_all = bool(kwargs.get("remove_all", False))
        effect_list = self._get_effect_list(owner_entity)
        if effect_list is None:
            return
        for effect_entity in list(effect_list.effect_entities):
            try:
                effect = self.world.component_for_entity(effect_entity, Effect)
            except KeyError:
                effect_list.effect_entities.remove(effect_entity)
                continue
            if slug is not None and effect.slug != slug:
                continue
            if stack_key is not None and effect.stack_key != stack_key:
                continue
            self._expire_effect(effect_entity, reason=reason)
            if not remove_all:
                break

    def on_turn_advanced(self, sender, **kwargs):
        previous_owner = kwargs.get("previous_owner")
        if previous_owner is None:
            return
        for effect_entity, components in list(self.world.get_components(Effect, EffectDuration)):
            effect_comp = cast(Effect, components[0])
            duration_comp = cast(EffectDuration, components[1])
            # Previously filtered by regiment owner; now just decrement all effects owned by previous owner entity.
            if effect_comp.owner_entity != previous_owner:
                continue
            duration_comp.remaining_turns -= 1
            if duration_comp.remaining_turns <= 0:
                self._expire_effect(effect_entity, reason="duration")

    def _ensure_effect_list(self, owner_entity: int) -> EffectList:
        try:
            return self.world.component_for_entity(owner_entity, EffectList)
        except KeyError:
            effect_list = EffectList()
            self.world.add_component(owner_entity, effect_list)
            return effect_list

    def _get_effect_list(self, owner_entity: int) -> EffectList | None:
        try:
            return self.world.component_for_entity(owner_entity, EffectList)
        except KeyError:
            return None

    def _find_effects(self, effect_list: EffectList, slug: str, stack_key: str | None) -> List[int]:
        matches: List[int] = []
        for effect_entity in effect_list.effect_entities:
            try:
                effect = self.world.component_for_entity(effect_entity, Effect)
            except KeyError:
                continue
            if effect.slug != slug:
                continue
            if stack_key is not None and effect.stack_key != stack_key:
                continue
            matches.append(effect_entity)
        return matches

    def _refresh_effect(
        self,
        effect_entity: int,
        metadata: Dict[str, Any],
        turns: Any,
        allow_multiple: bool,
        cumulative: bool,
        count_delta: int,
        stack_key: str | None,
        source_entity: int | None,
        expire_on_events: Iterable[str],
        expire_match_owner: bool,
        payload_owner_key: str,
    ) -> None:
        try:
            effect = self.world.component_for_entity(effect_entity, Effect)
        except KeyError:
            return
        effect.metadata.clear()
        effect.metadata.update(metadata)
        effect.allow_multiple = bool(allow_multiple)
        effect.stack_key = stack_key
        effect.cumulative = bool(cumulative)
        if count_delta:
            effect.count = max(0, int(count_delta))
        if source_entity is not None:
            effect.source_entity = source_entity
        if turns is not None:
            try:
                turns_value = int(turns)
            except (TypeError, ValueError):
                turns_value = 0
            try:
                duration_comp = self.world.component_for_entity(effect_entity, EffectDuration)
            except KeyError:
                self.world.add_component(effect_entity, EffectDuration(remaining_turns=max(0, turns_value)))
            else:
                duration_comp.remaining_turns = max(0, turns_value)
        else:
            self._remove_component(effect_entity, EffectDuration)
        self._unregister_event_triggers(effect_entity)
        expire_events_tuple = tuple(expire_on_events) if expire_on_events else ()
        if expire_events_tuple:
            try:
                expiry_comp = self.world.component_for_entity(effect_entity, EffectExpireOnEvents)
            except KeyError:
                self.world.add_component(
                    effect_entity,
                    EffectExpireOnEvents(
                        events=expire_events_tuple,
                        match_owner=expire_match_owner,
                        payload_owner_key=payload_owner_key,
                    ),
                )
            else:
                expiry_comp.events = expire_events_tuple
                expiry_comp.match_owner = expire_match_owner
                expiry_comp.payload_owner_key = payload_owner_key
            self._register_event_triggers(
                effect_entity,
                expire_events_tuple,
                expire_match_owner,
                payload_owner_key,
            )
        else:
            self._remove_component(effect_entity, EffectExpireOnEvents)
        self.event_bus.emit(
            EVENT_EFFECT_REFRESHED,
            effect_entity=effect_entity,
            owner_entity=effect.owner_entity,
            slug=effect.slug,
        )

    def _accumulate_effect(
        self,
        effect_entity: int,
        count_delta: int,
        metadata: Dict[str, Any],
        source_entity: int | None,
    ) -> None:
        try:
            effect = self.world.component_for_entity(effect_entity, Effect)
        except KeyError:
            return
        if count_delta:
            effect.count = max(0, effect.count + count_delta)
        effect.cumulative = True
        if metadata:
            effect.metadata.update(metadata)
        if source_entity is not None:
            effect.source_entity = source_entity
        self.event_bus.emit(
            EVENT_EFFECT_REFRESHED,
            effect_entity=effect_entity,
            owner_entity=effect.owner_entity,
            slug=effect.slug,
        )

    def _remove_component(self, entity: int, component_type) -> None:
        try:
            self.world.remove_component(entity, component_type)
        except Exception:
            pass

    def _expire_effect(self, effect_entity: int, reason: str) -> None:
        try:
            effect = self.world.component_for_entity(effect_entity, Effect)
        except KeyError:
            self._unregister_event_triggers(effect_entity)
            try:
                self.world.delete_entity(effect_entity)
            except Exception:
                pass
            return
        owner_entity = effect.owner_entity
        effect_list = self._get_effect_list(owner_entity)
        if effect_list and effect_entity in effect_list.effect_entities:
            effect_list.effect_entities.remove(effect_entity)
        self._unregister_event_triggers(effect_entity)
        try:
            self.world.delete_entity(effect_entity)
        except Exception:
            self._remove_component(effect_entity, Effect)
            self._remove_component(effect_entity, EffectDuration)
            self._remove_component(effect_entity, EffectExpireOnEvents)
        self.event_bus.emit(
            EVENT_EFFECT_EXPIRED,
            effect_entity=effect_entity,
            owner_entity=owner_entity,
            slug=effect.slug,
            reason=reason,
        )

    def _register_event_triggers(
        self,
        effect_entity: int,
        events: Iterable[str],
        match_owner: bool,
        payload_owner_key: str,
    ) -> None:
        for event_name in events:
            entries = self._event_triggers.setdefault(event_name, [])
            entries.append((effect_entity, match_owner, payload_owner_key))
            if event_name not in self._event_handlers:
                handler = self._make_event_handler(event_name)
                self._event_handlers[event_name] = handler
                self.event_bus.subscribe(event_name, handler)

    def _unregister_event_triggers(self, effect_entity: int) -> None:
        for event_name, entries in list(self._event_triggers.items()):
            filtered = [entry for entry in entries if entry[0] != effect_entity]
            if filtered:
                self._event_triggers[event_name] = filtered
            else:
                self._event_triggers.pop(event_name, None)

    def _make_event_handler(self, event_name: str) -> Callable:
        def handler(sender, **payload):
            self._handle_external_event(event_name, payload)

        return handler

    def _handle_external_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        entries = list(self._event_triggers.get(event_name, []))
        if not entries:
            return
        for effect_entity, match_owner, payload_owner_key in entries:
            try:
                effect = self.world.component_for_entity(effect_entity, Effect)
            except KeyError:
                continue
            if match_owner:
                owner_from_payload = payload.get(payload_owner_key)
                if owner_from_payload is None or owner_from_payload != effect.owner_entity:
                    continue
            self._expire_effect(effect_entity, reason=f"event:{event_name}")

    @staticmethod
    def _merge_metadata(definition: EffectDefinition | None, override: Dict[str, Any]) -> Dict[str, Any]:
        base: Dict[str, Any] = {}
        if definition is not None and definition.default_metadata:
            base.update(dict(definition.default_metadata))
        base.update(override)
        return base

    @staticmethod
    def _get_definition(slug: str) -> EffectDefinition | None:
        if default_effect_registry.has(slug):
            return default_effect_registry.get(slug)
        return None

    def process(self):
        # Lifecycle is event-driven; nothing to do per-frame beyond tick handling.
        return
