from esper import World

from ecs.events.bus import EventBus, EVENT_SKILL_POOL_OFFER, EVENT_SKILL_POOL_REQUEST
from ecs.factories.skills import create_skill_by_name
from ecs.systems.skills.skill_pool_system import SkillPoolSystem
from ecs.world import create_world
from ecs.components.skill_list_owner import SkillListOwner
from ecs.components.human_agent import HumanAgent


def _human_entity(world: World) -> int:
    return next(ent for ent, _ in world.get_component(HumanAgent))


def _skill_owner(world: World, entity: int) -> SkillListOwner:
    return world.component_for_entity(entity, SkillListOwner)


def test_skill_pool_request_excludes_owned_skills() -> None:
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    SkillPoolSystem(world, bus)
    owner = _human_entity(world)
    skill_owner = _skill_owner(world, owner)

    # Grant an additional skill manually to verify it is excluded from the offer.
    extra_skill = create_skill_by_name(world, "void_tithe")
    skill_owner.skill_entities.append(extra_skill)

    captured: dict = {}

    def capture(sender, **payload):
        captured.update(payload)

    bus.subscribe(EVENT_SKILL_POOL_OFFER, capture)

    bus.emit(
        EVENT_SKILL_POOL_REQUEST,
        owner_entity=owner,
        count=3,
        request_id="skills",
    )

    assert captured.get("owner_entity") == owner
    assert captured.get("request_id") == "skills"
    offers = captured.get("skills")
    assert offers is not None
    assert "self_reprimand" not in offers
    assert "void_tithe" not in offers
    assert set(offers) <= {"blood_covenant"}
    assert len(offers) == 1


def test_skill_pool_request_limits_total_offers() -> None:
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    pool = SkillPoolSystem(world, bus)
    owner = _human_entity(world)

    captured: dict = {}
    bus.subscribe(EVENT_SKILL_POOL_OFFER, lambda sender, **payload: captured.update(payload))

    bus.emit(
        EVENT_SKILL_POOL_REQUEST,
        owner_entity=owner,
        count=1,
        request_id=None,
    )

    offers = captured.get("skills")
    assert offers is not None
    assert len(offers) == 1

    known_names = pool.known_skill_names()
    assert offers[0] in known_names


def test_skill_pool_handles_missing_owner_component_gracefully() -> None:
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    SkillPoolSystem(world, bus)
    orphan = world.create_entity()

    captured: dict = {}
    bus.subscribe(EVENT_SKILL_POOL_OFFER, lambda sender, **payload: captured.update(payload))

    bus.emit(
        EVENT_SKILL_POOL_REQUEST,
        owner_entity=orphan,
        count=2,
    )

    offers = captured.get("skills")
    assert offers is not None
    assert len(offers) == 2
