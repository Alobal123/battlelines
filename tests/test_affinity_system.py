from ecs.events.bus import EventBus, EVENT_AFFINITY_UPDATED
from ecs.world import create_world
from ecs.components.affinity import Affinity
from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.human_agent import HumanAgent
from ecs.components.skill import Skill
from ecs.components.skill_list_owner import SkillListOwner
from ecs.systems.affinity_system import AffinitySystem


def _human_entity(world):
    humans = list(world.get_component(HumanAgent))
    assert humans, "Expected a human-controlled entity in the world"
    return humans[0][0]


def test_affinity_totals_include_base_abilities_and_skills():
    event_bus = EventBus()
    world = create_world(event_bus, grant_default_player_abilities=False, grant_default_player_skills=False)
    system = AffinitySystem(world, event_bus)

    player_entity = _human_entity(world)
    affinity = world.component_for_entity(player_entity, Affinity)
    assert affinity.totals == {"blood": 1, "spirit": 1}

    owner = world.component_for_entity(player_entity, AbilityListOwner)
    ability_entity = world.create_entity(
        Ability(
            name="test_bloodlash",
            kind="active",
            cost={"blood": 3, "hex": 1},
            affinity_bonus={"witchfire": 2},
        )
    )
    owner.ability_entities.append(ability_entity)

    skill_owner = world.component_for_entity(player_entity, SkillListOwner)
    skill_entity = world.create_entity(
        Skill(
            name="Blood Resonance",
            description="Enhances blood magic.",
            affinity_bonus={"blood": 2},
        )
    )
    skill_owner.skill_entities.append(skill_entity)

    captured: list[dict] = []

    def _capture(sender, **payload):
        captured.append(payload)

    event_bus.subscribe(EVENT_AFFINITY_UPDATED, _capture)
    system.recalculate_entity(player_entity)

    affinity = world.component_for_entity(player_entity, Affinity)
    assert affinity.totals == {"blood": 6, "hex": 1, "spirit": 1, "witchfire": 2}
    assert affinity.contributions["base"] == {"blood": 1, "spirit": 1}
    assert affinity.contributions["abilities"] == {"blood": 3, "hex": 1, "witchfire": 2}
    assert affinity.contributions["skills"] == {"blood": 2}
    assert len(affinity.breakdown) == 3

    assert captured, "Expected affinity update event to fire"
    last_payload = captured[-1]
    assert last_payload["owner_entity"] == player_entity
    assert last_payload["totals"] == affinity.totals