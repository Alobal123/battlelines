from esper import World

from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_POOL_OFFER,
    EVENT_ABILITY_POOL_REQUEST,
)
from ecs.factories.abilities import create_ability_by_name
from ecs.systems.ability_pool_system import AbilityPoolSystem
from ecs.world import create_world
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.ability import Ability
from ecs.components.human_agent import HumanAgent


def _human_entity(world: World) -> int:
    return next(ent for ent, _ in world.get_component(HumanAgent))


def _ability_owner(world: World, entity: int) -> AbilityListOwner:
    return world.component_for_entity(entity, AbilityListOwner)


def test_pool_request_excludes_owned_abilities():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    AbilityPoolSystem(world, bus)
    human = _human_entity(world)
    owner = _ability_owner(world, human)

    blood_bolt = create_ability_by_name(world, "blood_bolt")
    owner.ability_entities.append(blood_bolt)

    captured: dict = {}

    def capture(sender, **payload):
        captured.update(payload)

    bus.subscribe(EVENT_ABILITY_POOL_OFFER, capture)

    bus.emit(
        EVENT_ABILITY_POOL_REQUEST,
        owner_entity=human,
        count=3,
        request_id="req1",
    )

    assert captured.get("owner_entity") == human
    assert captured.get("request_id") == "req1"
    offered = captured.get("abilities")
    assert offered is not None
    assert "blood_bolt" not in offered
    assert set(offered) <= {"savagery", "spirit_leech", "verdant_touch"}
    # Three basic abilities remain after excluding the owned ability.
    assert len(offered) == 3


def test_pool_request_limits_total_offers():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    pool = AbilityPoolSystem(world, bus)
    human = _human_entity(world)

    captured: dict = {}
    bus.subscribe(EVENT_ABILITY_POOL_OFFER, lambda sender, **payload: captured.update(payload))

    bus.emit(
        EVENT_ABILITY_POOL_REQUEST,
        owner_entity=human,
        count=1,
        request_id=None,
    )

    offered = captured.get("abilities")
    assert offered is not None
    assert len(offered) == 1

    known_names = pool.known_ability_names()
    assert offered[0] in known_names


def test_pool_handles_missing_owner_component_gracefully():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    AbilityPoolSystem(world, bus)
    # Create a dummy entity without AbilityListOwner.
    orphan = world.create_entity()

    captured: dict = {}
    bus.subscribe(EVENT_ABILITY_POOL_OFFER, lambda sender, **payload: captured.update(payload))

    bus.emit(
        EVENT_ABILITY_POOL_REQUEST,
        owner_entity=orphan,
        count=2,
    )

    offered = captured.get("abilities")
    assert offered is not None
    assert len(offered) == 2
