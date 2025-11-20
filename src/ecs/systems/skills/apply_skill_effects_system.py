from __future__ import annotations

from esper import World

from ecs.components.skill_effect import SkillEffects
from ecs.components.skill_list_owner import SkillListOwner
from ecs.events.bus import EVENT_EFFECT_APPLY, EVENT_SKILL_CHOICE_GRANTED, EventBus


class ApplySkillEffectsSystem:
    """Applies passive skill effects when the system is constructed."""

    def __init__(self, world: World, event_bus: EventBus) -> None:
        self.world = world
        self.event_bus = event_bus
        self._apply_existing_skill_effects()
        self.event_bus.subscribe(EVENT_SKILL_CHOICE_GRANTED, self._on_skill_granted)

    def _apply_existing_skill_effects(self) -> None:
        for owner_entity, skill_list in self.world.get_component(SkillListOwner):
            for skill_entity in list(skill_list.skill_entities):
                self._apply_skill(skill_entity, owner_entity)

    def _apply_skill(self, skill_entity: int, owner_entity: int) -> None:
        try:
            effects: SkillEffects = self.world.component_for_entity(skill_entity, SkillEffects)
        except KeyError:
            return
        for spec in effects.effects:
            payload = {
                "owner_entity": owner_entity,
                "source_entity": skill_entity,
                "slug": spec.slug,
                "metadata": dict(spec.metadata),
            }
            if spec.turns is not None:
                payload["turns"] = spec.turns
            self.event_bus.emit(EVENT_EFFECT_APPLY, **payload)

    def _on_skill_granted(self, sender, **payload) -> None:
        owner_entity = payload.get("owner_entity")
        skill_entity = payload.get("skill_entity")
        if owner_entity is None or skill_entity is None:
            return
        self._apply_skill(int(skill_entity), int(owner_entity))
