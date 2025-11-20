from ecs.events.bus import EventBus
from ecs.world import create_world
from ecs.components.skill import Skill
from ecs.components.skill_effect import SkillEffects
from ecs.factories.player_skills import (
    create_skill_blood_covenant,
    create_skill_self_reprimand,
    create_skill_void_tithe,
)


def test_create_skill_self_reprimand_attaches_skill_metadata():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)

    skill_entity = create_skill_self_reprimand(world)

    skill: Skill = world.component_for_entity(skill_entity, Skill)
    assert skill.name == "Self Reprimand"
    assert "damage" in skill.description
    assert "blood" in skill.tags


def test_create_skill_self_reprimand_declares_effect():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)

    skill_entity = create_skill_self_reprimand(world)

    effects: SkillEffects = world.component_for_entity(skill_entity, SkillEffects)
    assert len(effects.effects) == 1
    spec = effects.effects[0]
    assert spec.slug == "self_reprimand"
    assert spec.turns is None
    assert spec.metadata == {}


def test_create_skill_void_tithe_metadata_and_effect():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)

    skill_entity = create_skill_void_tithe(world)

    skill: Skill = world.component_for_entity(skill_entity, Skill)
    assert skill.name == "Void Tithe"
    assert "empty" in skill.description

    effects: SkillEffects = world.component_for_entity(skill_entity, SkillEffects)
    assert len(effects.effects) == 1
    spec = effects.effects[0]
    assert spec.slug == "void_tithe"
    assert spec.turns is None
    assert spec.metadata == {}


def test_create_skill_blood_covenant_metadata_and_effect():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)

    skill_entity = create_skill_blood_covenant(world)

    skill: Skill = world.component_for_entity(skill_entity, Skill)
    assert skill.name == "Blood Covenant"
    assert "start" in skill.description.lower()

    effects: SkillEffects = world.component_for_entity(skill_entity, SkillEffects)
    assert len(effects.effects) == 1
    spec = effects.effects[0]
    assert spec.slug == "blood_covenant"
    assert spec.turns is None
    assert spec.metadata == {}
