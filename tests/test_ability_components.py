from ecs.events.bus import EventBus
from ecs.world import create_world
from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.human_agent import HumanAgent

from tests.helpers import grant_player_abilities


def test_ability_entity_created():
    bus = EventBus()
    world = create_world(bus)
    grant_player_abilities(world, ("tactical_shift",))
    # Find ability entity via Ability component
    ability_entities = list(world.get_component(Ability))
    assert ability_entities, "Ability entity not created"
    ent, ability = next(
        (entity, ability)
        for entity, ability in ability_entities
        if ability.name == "tactical_shift"
    )
    assert ability.name == "tactical_shift"
    assert ability.kind == "active"
    assert ability.cost == {"hex": 3, "nature": 2}
    # Confirm targeting component paired
    target = world.component_for_entity(ent, AbilityTarget)
    assert target.target_type == "tile"
    assert target.max_targets == 1


def test_player_has_ability_list_owner():
    bus = EventBus()
    world = create_world(bus)
    grant_player_abilities(world, ("tactical_shift",))
    human_entities = list(world.get_component(HumanAgent))
    assert human_entities, "Player AbilityListOwner not found"
    player_ent = human_entities[0][0]
    owner = world.component_for_entity(player_ent, AbilityListOwner)
    assert owner.ability_entities, "No abilities referenced"
    first_ability_ent = owner.ability_entities[0]
    ability = world.component_for_entity(first_ability_ent, Ability)
    assert ability.name == "tactical_shift"
