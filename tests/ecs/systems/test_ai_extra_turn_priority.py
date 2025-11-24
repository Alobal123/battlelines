import random

from ecs.events.bus import EventBus
from ecs.systems.rule_based_ai_system import RuleBasedAISystem
from world import create_world
from ecs.systems.board import BoardSystem
from ecs.systems.match import MatchSystem
from ecs.systems.animation import AnimationSystem
from ecs.systems.render import RenderSystem
from ecs.systems.match_resolution import MatchResolutionSystem
from ecs.systems.turn_system import TurnSystem
from ecs.systems.board_ops import find_valid_swaps
from ecs.components.turn_order import TurnOrder
from ecs.components.active_turn import ActiveTurn
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.tile_types import TileTypes
from ecs.components.tile import TileType
from ecs.components.board_position import BoardPosition
from ecs.components.board import Board
from ecs.factories.abilities import create_ability_by_name
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.tile_bank import TileBank
from ecs.components.ability import Ability
from ecs.components.health import Health
from ecs.ai.simulation import clone_world_state
from typing import cast, Tuple


class DummyWindow:
    def __init__(self):
        self.width = 800
        self.height = 600


def _configure_world():
    bus = EventBus()
    world = create_world(bus)
    window = DummyWindow()
    board = BoardSystem(world, bus, rows=5, cols=5)
    MatchSystem(world, bus)
    AnimationSystem(world, bus)
    RenderSystem(world, bus, window)
    MatchResolutionSystem(world, bus)
    turn_system = TurnSystem(world, bus)
    return world, bus, board, turn_system


def _set_board_pattern(world, board_system, layout):
    board: Board = world.component_for_entity(board_system.board_entity, Board)
    assert len(layout) == board.rows
    assert all(len(row) == board.cols for row in layout)
    for row_idx, row in enumerate(layout):
        for col_idx, type_name in enumerate(row):
            ent = board_system._get_entity_at(row_idx, col_idx)
            tile = world.component_for_entity(ent, TileType)
            tile.type_name = type_name


def _ai_owner(world):
    for ent, _ in world.get_component(RuleBasedAgent):
        return ent
    raise AssertionError("AI owner not found")


def _swap_generates_extra_turn(world, owner_entity, swap):
    clone_state = clone_world_state(world)
    clone_owner = clone_state.entity_map.get(owner_entity, owner_entity)
    clone_state.engine.swap_and_resolve(*swap, acting_owner=clone_owner)
    return clone_state.engine.last_action_generated_extra_turn


def test_ai_prefers_extra_turn_swap_over_other_options():
    world, bus, board_system, turn_system = _configure_world()
    ai_owner = _ai_owner(world)
    order_entry = next(iter(world.get_component(TurnOrder)))
    order_comp = order_entry[1]
    assert ai_owner in order_comp.owners
    order_comp.index = order_comp.owners.index(ai_owner)
    active_entry = next(iter(world.get_component(ActiveTurn)))
    active_entry[1].owner_entity = ai_owner

    tile_types = next(iter(world.get_component(TileTypes)))[1].all_types()
    a, b, c, d, e, f, g = tile_types[:7]
    layout = [
        [a, b, c, d, e],
        [a, b, c, d, e],
        [g, f, g, g, g],
        [a, b, c, d, e],
        [a, b, c, d, e],
    ]
    _set_board_pattern(world, board_system, layout)

    swaps = find_valid_swaps(world)
    assert swaps
    extra_turn_swaps = [swap for swap in swaps if _swap_generates_extra_turn(world, ai_owner, swap)]
    assert extra_turn_swaps
    non_extra_turn_swaps = [swap for swap in swaps if swap not in extra_turn_swaps]
    assert non_extra_turn_swaps

    owner_comp: AbilityListOwner = world.component_for_entity(ai_owner, AbilityListOwner)
    ability_entity = create_ability_by_name(world, "blood_bolt")
    owner_comp.ability_entities.append(ability_entity)
    ability: Ability = world.component_for_entity(ability_entity, Ability)
    ability.ends_turn = True
    bank = world.component_for_entity(ai_owner, TileBank)
    for type_name, amount in ability.cost.items():
        bank.counts[type_name] = max(bank.counts.get(type_name, 0), amount)
    opponent = next(ent for ent, _ in world.get_component(Health) if ent != ai_owner)
    opp_health: Health = world.component_for_entity(opponent, Health)
    opp_health.current = 50

    ai = RuleBasedAISystem(world, bus, rng=random.Random(1))
    ability_actions = ai._enumerate_ability_actions(ai_owner)
    assert any(action.ability_entity == ability_entity for action in ability_actions)

    swap_action = ai._choose_action(ai_owner)
    assert swap_action is not None
    kind, payload = swap_action
    assert kind == "swap"
    swap_payload = cast(Tuple[Tuple[int, int], Tuple[int, int]], payload)
    src, dst = swap_payload
    assert _swap_generates_extra_turn(world, ai_owner, (src, dst))
