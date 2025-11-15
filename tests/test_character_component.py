from ecs.world import create_world
from ecs.events.bus import EventBus
from ecs.components.character import Character
from ecs.components.ability_list_owner import AbilityListOwner


def test_character_component_on_players():
    """Verify that Character components are correctly assigned to players."""
    bus = EventBus()
    world = create_world(bus)
    
    # Get all players with character components
    characters = list(world.get_component(Character))
    assert len(characters) == 2, "Should have 2 characters"
    
    # Create a mapping by slug for order-independent testing
    char_by_slug = {char.slug: (entity, char) for entity, char in characters}
    
    # Verify Fiora exists
    assert "fiora" in char_by_slug
    fiora_entity, fiora = char_by_slug["fiora"]
    assert fiora.name == "Fiora"
    assert fiora.description == "A young witch mastering the arcane arts"
    assert fiora.portrait_path == "fiora.png"
    
    # Verify Undead Gardener exists
    assert "undead_gardener" in char_by_slug
    gardener_entity, gardener = char_by_slug["undead_gardener"]
    assert gardener.name == "Undead Gardener"
    assert gardener.description == "A mysterious caretaker of forgotten groves"
    assert gardener.portrait_path == "undead_gardener.png"
    
    # Verify characters are attached to ability owners
    owners = list(world.get_component(AbilityListOwner))
    assert len(owners) == 2
    
    owner_entities = {ent for ent, _ in owners}
    character_entities = {fiora_entity, gardener_entity}
    assert owner_entities == character_entities, "Character entities should match owner entities"
