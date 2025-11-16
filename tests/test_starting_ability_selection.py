from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.game_state import GameMode, GameState
from ecs.components.human_agent import HumanAgent
from ecs.components.starting_ability_choice import StartingAbilityChoice
from ecs.events.bus import EVENT_CHOICE_SELECTED, EventBus
from ecs.factories.abilities import spawn_starting_ability_choice
from ecs.systems.ability_starting_system import AbilityStartingSystem
from ecs.world import create_world


def _human_entity(world: World) -> int:
    return next(ent for ent, _ in world.get_component(HumanAgent))


def test_spawn_starting_ability_choice_creates_options():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    window_entity = spawn_starting_ability_choice(world)
    assert window_entity is not None
    choices = list(world.get_component(StartingAbilityChoice))
    assert len(choices) == 3
    state = next(comp for _, comp in world.get_component(GameState))
    assert state.mode == GameMode.ABILITY_DRAFT


def test_starting_ability_selection_adds_chosen_ability():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    AbilityStartingSystem(world, bus)
    window_entity = spawn_starting_ability_choice(world)
    state = next(comp for _, comp in world.get_component(GameState))
    assert state.mode == GameMode.ABILITY_DRAFT
    choice_entity = next(
        ent
        for ent, choice in world.get_component(StartingAbilityChoice)
        if choice.ability_name == "verdant_touch"
    )
    bus.emit(EVENT_CHOICE_SELECTED, window_entity=window_entity, choice_entity=choice_entity)
    assert state.mode == GameMode.COMBAT
    owner_entity = _human_entity(world)
    owner_comp: AbilityListOwner = world.component_for_entity(owner_entity, AbilityListOwner)
    assert len(owner_comp.ability_entities) == 1
    ability_entity = owner_comp.ability_entities[0]
    ability = world.component_for_entity(ability_entity, Ability)
    assert ability.name == "verdant_touch"
    assert not list(world.get_component(StartingAbilityChoice))
