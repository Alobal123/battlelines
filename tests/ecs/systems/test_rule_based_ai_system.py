import random
from typing import cast

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.active_switch import ActiveSwitch
from ecs.components.board import Board
from ecs.components.board_position import BoardPosition
from ecs.components.health import Health
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.tile import TileType
from ecs.events.bus import EventBus
from ecs.systems.base_ai_system import AbilityAction
from ecs.systems.rule_based_ai_system import RuleBasedAISystem
from ecs.systems.board_ops import find_valid_swaps
from ecs.world import create_world


def _build_board(world: World, layout: list[list[str]]) -> None:
    rows = len(layout)
    cols = len(layout[0]) if rows else 0
    world.create_entity(Board(rows=rows, cols=cols))
    for r, row in enumerate(layout):
        for c, type_name in enumerate(row):
            world.create_entity(
                BoardPosition(row=r, col=c),
                TileType(type_name=type_name),
                ActiveSwitch(active=True),
            )


def _get_ability_entity(world: World, owner: int, ability_name: str) -> int:
    owner_comp: AbilityListOwner = world.component_for_entity(owner, AbilityListOwner)
    for ability_entity in owner_comp.ability_entities:
        ability = world.component_for_entity(ability_entity, Ability)
        if ability.name == ability_name:
            return ability_entity
    raise AssertionError(f"Ability {ability_name} not found for owner {owner}")


def test_rule_based_ai_prefers_lethal_ability_over_swap():
    bus = EventBus()
    world = create_world(bus)
    layout = [
        ["spirit", "nature", "hex"],
        ["blood", "hex", "secrets"],
        ["secrets", "hex", "blood"],
    ]
    _build_board(world, layout)
    ai_owner = next(ent for ent, _ in world.get_component(RuleBasedAgent))
    ability_entity = _get_ability_entity(world, ai_owner, "blood_bolt")
    owner_comp: AbilityListOwner = world.component_for_entity(ai_owner, AbilityListOwner)
    owner_comp.ability_entities = [ability_entity]
    # Set opponent low enough for blood_bolt to be lethal.
    opponent_entity = next(ent for ent, _ in world.get_component(Health) if ent != ai_owner)
    opponent_health: Health = world.component_for_entity(opponent_entity, Health)
    opponent_health.current = 5
    ai_system = RuleBasedAISystem(world, bus, rng=random.Random(0))

    # Ensure there is at least one valid swap candidate as an alternative option.
    assert find_valid_swaps(world), "Expected at least one swap candidate"

    action = ai_system._choose_action(ai_owner)
    assert action is not None
    kind, payload = action
    assert kind == "ability"
    ability_payload = cast(AbilityAction, payload)
    assert ability_payload.ability_entity == ability_entity


def test_rule_based_ai_prioritises_witchfire_targets():
    bus = EventBus()
    world = create_world(bus)
    layout = [
        ["witchfire", "nature", "hex", "blood"],
        ["nature", "hex", "blood", "hex"],
        ["spirit", "nature", "hex", "nature"],
        ["blood", "hex", "nature", "secrets"],
    ]
    _build_board(world, layout)
    ai_owner = next(ent for ent, _ in world.get_component(RuleBasedAgent))
    ability_entity = _get_ability_entity(world, ai_owner, "crimson_pulse")
    owner_comp: AbilityListOwner = world.component_for_entity(ai_owner, AbilityListOwner)
    owner_comp.ability_entities = [ability_entity]
    ai_system = RuleBasedAISystem(world, bus, rng=random.Random(0))

    actions = ai_system._enumerate_ability_actions(ai_owner)
    witchfire_action = next(
        action
        for action in actions
        if action.ability_entity == ability_entity and action.target == (0, 0)
    )
    distant_action = next(
        action
        for action in actions
        if action.ability_entity == ability_entity and action.target == (3, 3)
    )

    score_witchfire = ai_system._score_action(ai_owner, ("ability", witchfire_action))
    score_distant = ai_system._score_action(ai_owner, ("ability", distant_action))

    assert score_witchfire > score_distant


def test_rule_based_ai_prefers_higher_cost_ready_ability():
    bus = EventBus()
    world = create_world(bus)
    ai_owner = next(ent for ent, _ in world.get_component(RuleBasedAgent))
    ferality_entity = _get_ability_entity(world, ai_owner, "ferality")
    blood_bolt_entity = _get_ability_entity(world, ai_owner, "blood_bolt")
    owner_comp: AbilityListOwner = world.component_for_entity(ai_owner, AbilityListOwner)
    owner_comp.ability_entities = [ferality_entity, blood_bolt_entity]
    opponent_entity = next(ent for ent, _ in world.get_component(Health) if ent != ai_owner)
    opponent_health: Health = world.component_for_entity(opponent_entity, Health)
    opponent_health.current = 20
    ai_system = RuleBasedAISystem(world, bus, rng=random.Random(0))

    actions = ai_system._enumerate_ability_actions(ai_owner)
    ferality_action = next(
        action for action in actions if action.ability_entity == ferality_entity
    )
    blood_bolt_action = next(
        action for action in actions if action.ability_entity == blood_bolt_entity
    )

    score_ferality = ai_system._score_action(ai_owner, ("ability", ferality_action))
    score_blood_bolt = ai_system._score_action(ai_owner, ("ability", blood_bolt_action))

    assert score_blood_bolt > score_ferality
