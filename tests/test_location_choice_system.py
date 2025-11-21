from ecs.components.human_agent import HumanAgent
from ecs.components.location import CurrentLocation, LocationChoice
from ecs.events.bus import EVENT_CHOICE_SELECTED, EVENT_LOCATION_CHOICE_GRANTED, EventBus
from ecs.factories.locations import spawn_location_choice_window
from ecs.systems.location_choice_system import LocationChoiceSystem
from ecs.world import create_world


def _human_entity(world):
    return next(ent for ent, _ in world.get_component(HumanAgent))


def test_location_choice_emits_event_and_updates_owner():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    LocationChoiceSystem(world, bus)
    owner_entity = _human_entity(world)

    window_entity = spawn_location_choice_window(world, owner_entity=owner_entity, event_bus=bus)
    assert window_entity is not None

    choices = list(world.get_component(LocationChoice))
    assert choices
    choice_entity, choice_comp = choices[0]

    captured: dict = {}
    bus.subscribe(EVENT_LOCATION_CHOICE_GRANTED, lambda sender, **payload: captured.update(payload))

    bus.emit(
        EVENT_CHOICE_SELECTED,
        window_entity=window_entity,
        choice_entity=choice_entity,
        press_id=321,
    )

    current = world.component_for_entity(owner_entity, CurrentLocation)
    assert current.slug == choice_comp.location_slug
    assert captured.get("owner_entity") == owner_entity
    assert captured.get("location_slug") == choice_comp.location_slug
