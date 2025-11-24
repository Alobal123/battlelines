"""Tests for the Arcane Library location and its denizens."""
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.character import Character
from ecs.events.bus import EventBus
from ecs.factories.locations import get_location_spec
from world import create_world


def test_arcane_library_location_exists():
    """Ensure arcane_library location is registered."""
    spec = get_location_spec("arcane_library")
    assert spec is not None
    assert spec.slug == "arcane_library"
    assert spec.name == "Arcane Library"
    assert "library" in spec.description.lower()
    assert spec.enemy_names == ("grimoire", "codex", "librarian")


def test_arcane_library_enemies_spawn_without_abilities():
    """Arcane Library enemies should spawn and lack abilities by default."""
    bus = EventBus()
    world = create_world(bus)
    enemy_pool = getattr(world, "enemy_pool")

    for slug, expected_name in (
        ("grimoire", "Bound Grimoire"),
        ("codex", "Living Codex"),
        ("librarian", "Arcane Librarian"),
    ):
        assert slug in enemy_pool.known_enemy_names()
        enemy_entity = enemy_pool.create_enemy(slug)
        char = world.component_for_entity(enemy_entity, Character)
        abilities = world.component_for_entity(enemy_entity, AbilityListOwner)

        assert char.slug == slug
        assert char.name == expected_name
        assert abilities.ability_entities == []


def test_arcane_library_in_location_pool():
    """Arcane Library should appear among offered locations."""
    bus = EventBus()
    world = create_world(bus)
    location_pool = getattr(world, "location_pool")

    locations = location_pool.known_location_slugs()
    assert "arcane_library" in locations
    assert len(locations) >= 3
