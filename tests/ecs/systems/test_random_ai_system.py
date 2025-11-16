import random

from esper import World

from ecs.components.active_switch import ActiveSwitch
from ecs.components.board import Board
from ecs.components.board_position import BoardPosition
from ecs.components.tile import TileType
from ecs.components.tile_bank import TileBank
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.random_agent import RandomAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.ability import Ability
from ecs.events.bus import (
    EVENT_ABILITY_ACTIVATE_REQUEST,
    EVENT_TILE_SWAP_REQUEST,
    EVENT_TICK,
    EVENT_TURN_ADVANCED,
    EventBus,
)
from ecs.systems.board import BoardSystem
from ecs.systems.board_ops import find_valid_swaps
from ecs.systems.random_ai_system import RandomAISystem
from ecs.world import create_world


def _build_board(world: World, layout, board_system: BoardSystem | None = None):
    rows = len(layout)
    cols = len(layout[0]) if rows else 0
    if board_system is None:
        world.create_entity(Board(rows=rows, cols=cols))
        for r, row in enumerate(layout):
            for c, type_name in enumerate(row):
                world.create_entity(
                    BoardPosition(row=r, col=c),
                    TileType(type_name=type_name),
                    ActiveSwitch(active=True),
                )
    else:
        for r, row in enumerate(layout):
            for c, type_name in enumerate(row):
                ent = board_system._get_entity_at(r, c)
                assert ent is not None
                world.component_for_entity(ent, TileType).type_name = type_name
                world.component_for_entity(ent, ActiveSwitch).active = True


def test_find_valid_swaps_identifies_vertical_match():
    world = World()
    layout = [
        ["spirit", "nature", "hex"],
        ["blood", "hex", "secrets"],
        ["secrets", "hex", "blood"],
    ]
    _build_board(world, layout)
    swaps = find_valid_swaps(world)
    assert swaps == [((0, 1), (0, 2))]


def test_random_ai_emits_swap_when_available():
    bus = EventBus()
    world = create_world(bus)
    board_system = BoardSystem(world, bus, rows=3, cols=3)
    ai_owner = next(ent for ent, _ in world.get_component(RuleBasedAgent))
    world.add_component(ai_owner, RandomAgent())
    agent_comp: RandomAgent = world.component_for_entity(ai_owner, RandomAgent)
    agent_comp.decision_delay = 0.0
    agent_comp.selection_delay = 0.0
    # Remove abilities so only swaps are considered.
    owner_comp: AbilityListOwner = world.component_for_entity(ai_owner, AbilityListOwner)
    owner_comp.ability_entities = []
    layout = [
        ["spirit", "nature", "hex"],
        ["blood", "hex", "secrets"],
        ["secrets", "hex", "blood"],
    ]
    _build_board(world, layout, board_system)
    captured = {}

    def record_swap(sender, **payload):
        captured["swap"] = (payload.get("src"), payload.get("dst"))

    bus.subscribe(EVENT_TILE_SWAP_REQUEST, record_swap)
    RandomAISystem(world, bus, rng=random.Random(0))

    bus.emit(EVENT_TURN_ADVANCED, previous_owner=None, new_owner=ai_owner)
    bus.emit(EVENT_TICK, dt=1 / 60)

    assert "swap" in captured
    assert captured["swap"] == ((0, 1), (0, 2))


def test_random_ai_triggers_self_ability_when_no_swaps():
    bus = EventBus()
    world = create_world(bus)
    board_system = BoardSystem(world, bus, rows=1, cols=1)
    ai_owner = next(ent for ent, _ in world.get_component(RuleBasedAgent))
    world.add_component(ai_owner, RandomAgent())
    agent_comp: RandomAgent = world.component_for_entity(ai_owner, RandomAgent)
    agent_comp.decision_delay = 0.0
    agent_comp.selection_delay = 0.0
    owner_comp: AbilityListOwner = world.component_for_entity(ai_owner, AbilityListOwner)
    # Limit to shovel_punch (self-target ability) for determinism.
    shovel_punch_entity = next(
        ent
        for ent in owner_comp.ability_entities
        if world.component_for_entity(ent, Ability).name == "shovel_punch"
    )
    owner_comp.ability_entities = [shovel_punch_entity]
    # Give the AI enough mana to use the ability
    bank = world.component_for_entity(ai_owner, TileBank)
    bank.counts["shapeshift"] = 10
    bank.counts["nature"] = 10
    # 1x1 board ensures no valid swap actions exist.
    _build_board(world, [["nature"]], board_system)
    captured = {}

    def record_ability(sender, **payload):
        captured["ability"] = payload

    bus.subscribe(EVENT_ABILITY_ACTIVATE_REQUEST, record_ability)
    RandomAISystem(world, bus, rng=random.Random(0))

    bus.emit(EVENT_TURN_ADVANCED, previous_owner=None, new_owner=ai_owner)
    bus.emit(EVENT_TICK, dt=1 / 60)

    assert "ability" in captured
    assert captured["ability"]["ability_entity"] == shovel_punch_entity
    assert captured["ability"]["owner_entity"] == ai_owner
