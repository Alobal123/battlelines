"""Test that School Kennels location and its enemies are properly registered."""
from ecs.events.bus import EventBus
from ecs.factories.locations import get_location_spec
from world import create_world


def test_school_kennels_location_exists():
    """Test that school_kennels location is registered."""
    spec = get_location_spec("school_kennels")
    assert spec is not None
    assert spec.slug == "school_kennels"
    assert spec.name == "School Kennels"
    assert "barks" in spec.description.lower() or "training" in spec.description.lower()
    assert len(spec.enemy_names) == 3


def test_school_kennels_enemy_names():
    """Test that school_kennels has the correct enemy assignments."""
    spec = get_location_spec("school_kennels")
    assert spec is not None
    assert "kennelmaster" in spec.enemy_names
    assert "mastiffs" in spec.enemy_names
    assert "bloodhound" in spec.enemy_names


def test_kennelmaster_enemy_spawns():
    """Test that kennelmaster enemy can be spawned."""
    bus = EventBus()
    world = create_world(bus)
    enemy_pool = getattr(world, "enemy_pool")
    
    assert "kennelmaster" in enemy_pool.known_enemy_names()
    enemy_entity = enemy_pool.create_enemy("kennelmaster")
    assert enemy_entity is not None
    
    from ecs.components.character import Character
    char = world.component_for_entity(enemy_entity, Character)
    assert char.slug == "kennelmaster"
    assert char.name == "Kennelmaster"


def test_mastiffs_enemy_spawns():
    """Test that mastiffs enemy can be spawned."""
    bus = EventBus()
    world = create_world(bus)
    enemy_pool = getattr(world, "enemy_pool")
    
    assert "mastiffs" in enemy_pool.known_enemy_names()
    enemy_entity = enemy_pool.create_enemy("mastiffs")
    assert enemy_entity is not None
    
    from ecs.components.character import Character
    char = world.component_for_entity(enemy_entity, Character)
    assert char.slug == "mastiffs"
    assert char.name == "Guarding Mastiffs"


def test_mastiffs_has_guard_and_mighty_bark():
    bus = EventBus()
    world = create_world(bus)
    enemy_pool = getattr(world, "enemy_pool")

    enemy_entity = enemy_pool.create_enemy("mastiffs")

    from ecs.components.ability import Ability
    from ecs.components.ability_effect import AbilityEffects
    from ecs.components.ability_list_owner import AbilityListOwner

    owner = world.component_for_entity(enemy_entity, AbilityListOwner)
    assert owner.ability_entities, "Expected mastiffs to have an ability equipped"

    ability_entities = {
        world.component_for_entity(ent, Ability).name: ent for ent in owner.ability_entities
    }

    assert "guard" in ability_entities, "Mastiffs should be configured with guard"
    assert "mighty_bark" in ability_entities, "Mastiffs should be configured with mighty_bark"

    guard = world.component_for_entity(ability_entities["guard"], Ability)
    assert guard.cost == {"shapeshift": 3}
    assert guard.ends_turn is True
    assert "guarded tiles" in guard.description.lower()

    mighty_bark = world.component_for_entity(ability_entities["mighty_bark"], Ability)
    assert mighty_bark.cost == {"shapeshift": 4}
    assert mighty_bark.ends_turn is True
    assert mighty_bark.params.get("heal_per_tile") == 2


def test_bloodhound_enemy_spawns():
    """Test that bloodhound enemy can be spawned."""
    bus = EventBus()
    world = create_world(bus)
    enemy_pool = getattr(world, "enemy_pool")
    
    assert "bloodhound" in enemy_pool.known_enemy_names()
    enemy_entity = enemy_pool.create_enemy("bloodhound")
    assert enemy_entity is not None
    
    from ecs.components.character import Character
    char = world.component_for_entity(enemy_entity, Character)
    assert char.slug == "bloodhound"
    assert char.name == "Feral Bloodhound"


def test_school_kennels_in_location_pool():
    """Test that school_kennels appears in location pool."""
    bus = EventBus()
    world = create_world(bus)
    location_pool = getattr(world, "location_pool")
    
    locations = location_pool.known_location_slugs()
    assert "school_kennels" in locations
    assert len(locations) >= 3  # skeletal_garden + school_kennels + arcane_library


def test_bloodhound_scent_lock_inflicts_bleeding():
    bus = EventBus()
    world = create_world(bus)
    enemy_pool = getattr(world, "enemy_pool")

    enemy_entity = enemy_pool.create_enemy("bloodhound")

    from ecs.components.ability import Ability
    from ecs.components.ability_effect import AbilityEffects
    from ecs.components.ability_list_owner import AbilityListOwner

    owner = world.component_for_entity(enemy_entity, AbilityListOwner)
    assert owner.ability_entities, "Expected bloodhound to have at least one ability"

    ability_by_name = {}
    for ability_entity in owner.ability_entities:
        ability = world.component_for_entity(ability_entity, Ability)
        ability_by_name[ability.name] = ability_entity

    assert "scent_lock" in ability_by_name, "Bloodhound should be configured with the scent_lock ability"
    assert "go_for_throat" in ability_by_name, "Bloodhound should also be configured with go_for_throat"

    scent_lock = world.component_for_entity(ability_by_name["scent_lock"], Ability)
    assert scent_lock.cost == {"blood": 2, "shapeshift": 2}
    assert scent_lock.ends_turn is False
    assert scent_lock.cooldown == 1

    scent_effects = world.component_for_entity(ability_by_name["scent_lock"], AbilityEffects)
    assert scent_effects.effects, "scent_lock should apply at least one effect"
    scent_spec = scent_effects.effects[0]
    assert scent_spec.slug == "bleeding"
    assert scent_spec.target == "opponent"
    assert scent_spec.metadata.get("count") == 5
    assert scent_spec.metadata.get("reason") == "scent_lock"

    go_for_throat = world.component_for_entity(ability_by_name["go_for_throat"], Ability)
    assert go_for_throat.cost == {"shapeshift": 7}
    assert go_for_throat.ends_turn is True

    throat_effects = world.component_for_entity(ability_by_name["go_for_throat"], AbilityEffects)
    assert throat_effects.effects, "go_for_throat should apply a damage effect"
    throat_spec = throat_effects.effects[0]
    assert throat_spec.slug == "damage"
    assert throat_spec.target == "opponent"
    assert throat_spec.metadata.get("reason") == "go_for_throat"
