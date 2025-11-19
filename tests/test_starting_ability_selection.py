import random

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.game_state import GameMode, GameState
from ecs.components.human_agent import HumanAgent
from ecs.components.starting_ability_choice import AbilityChoice
from ecs.components.dialogue_session import DialogueSession
from ecs.events.bus import EVENT_CHOICE_SELECTED, EventBus
from ecs.factories.abilities import spawn_player_ability_choice
from ecs.systems.match_setup_system import MatchSetupSystem
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.dialogue_system import DialogueSystem
from ecs.world import create_world


def _human_entity(world: World) -> int:
    return next(ent for ent, _ in world.get_component(HumanAgent))


def test_spawn_player_ability_choice_creates_options():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    window_entity = spawn_player_ability_choice(
        world,
        rng=random.Random(0),
        require_empty_owner=True,
        title="Choose Your First Ability",
    )
    assert window_entity is not None
    choices = list(world.get_component(AbilityChoice))
    assert len(choices) == 3
    state = next(comp for _, comp in world.get_component(GameState))
    assert state.mode == GameMode.ABILITY_DRAFT


def test_player_ability_selection_adds_chosen_ability():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    DialogueSystem(world, bus)
    AbilitySystem(world, bus)
    MatchSetupSystem(world, bus, rng=random.Random(1))
    window_entity = spawn_player_ability_choice(
        world,
        rng=random.Random(1),
        require_empty_owner=True,
        title="Choose Your First Ability",
    )
    state = next(comp for _, comp in world.get_component(GameState))
    assert state.mode == GameMode.ABILITY_DRAFT
    choices = list(world.get_component(AbilityChoice))
    assert choices, "Expected at least one starting ability option"
    choice_entity, choice_comp = choices[0]
    selected_name = choice_comp.ability_name
    bus.emit(
        EVENT_CHOICE_SELECTED,
        window_entity=window_entity,
        choice_entity=choice_entity,
        press_id=777,
    )
    assert state.mode == GameMode.DIALOGUE
    owner_entity = _human_entity(world)
    owner_comp: AbilityListOwner = world.component_for_entity(owner_entity, AbilityListOwner)
    assert len(owner_comp.ability_entities) == 1
    ability_entity = owner_comp.ability_entities[0]
    ability = world.component_for_entity(ability_entity, Ability)
    assert ability.name == selected_name
    assert not list(world.get_component(AbilityChoice))
    sessions = list(world.get_component(DialogueSession))
    assert sessions
    _, session = sessions[0]
    assert session.current_index == 0
