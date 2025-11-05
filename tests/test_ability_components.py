from ecs.events.bus import EventBus
from ecs.world import create_world
from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.ability_list_owner import AbilityListOwner


def test_ability_entity_created():
    bus = EventBus()
    world = create_world(bus)
    # Find ability entity via Ability component
    ability_entities = list(world.get_component(Ability))
    assert ability_entities, "Ability entity not created"
    ent, ability = ability_entities[0]
    assert ability.name == "tactical_shift"
    assert ability.kind == "active"
    assert ability.cost == {"red": 3, "blue": 2}
    # Confirm targeting component paired
    target = world.component_for_entity(ent, AbilityTarget)
    assert target.target_type == "tile"
    assert target.max_targets == 1


def test_player_has_ability_list_owner():
    bus = EventBus()
    world = create_world(bus)
    owners = list(world.get_component(AbilityListOwner))
    assert owners, "Player AbilityListOwner not found"
    player_ent, owner = owners[0]
    assert owner.ability_entities, "No abilities referenced"
    first_ability_ent = owner.ability_entities[0]
    ability = world.component_for_entity(first_ability_ent, Ability)
    assert ability.name == "tactical_shift"
