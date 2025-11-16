import pytest
from ecs.events.bus import EventBus, EVENT_ABILITY_ACTIVATE_REQUEST, EVENT_TILE_BANK_SPENT, EVENT_ABILITY_TARGET_SELECTED, EVENT_TILE_CLICK, EVENT_CASCADE_COMPLETE, EVENT_TURN_ADVANCED, EVENT_TICK, EVENT_CASCADE_STEP, EVENT_MATCH_FOUND, EVENT_TURN_ACTION_STARTED
from ecs.world import create_world
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.ability_targeting_system import AbilityTargetingSystem
from ecs.systems.turn_system import TurnSystem
from ecs.systems.tile_bank_system import TileBankSystem
from ecs.systems.board import BoardSystem
from ecs.systems.match import MatchSystem
from ecs.systems.match_resolution import MatchResolutionSystem
from ecs.systems.animation import AnimationSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.board_clear_effect_system import BoardClearEffectSystem
from ecs.systems.effects.board_transform_effect_system import BoardTransformEffectSystem
from ecs.components.active_turn import ActiveTurn
from ecs.components.turn_order import TurnOrder
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.human_agent import HumanAgent
from ecs.components.ability import Ability
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.targeting_state import TargetingState
from ecs.components.turn_state import TurnState
from ecs.components.board_position import BoardPosition
from ecs.components.tile import TileType

# This test ensures that an ability that produces a board change but NO matches still ends the turn.
# We'll trigger tactical_shift on a tile color that after conversion creates no matches.

@pytest.fixture
def setup_world():
    bus = EventBus(); world = create_world(bus)
    AbilityTargetingSystem(world, bus)
    AbilitySystem(world, bus)
    TileBankSystem(world, bus)
    turn = TurnSystem(world, bus)
    BoardSystem(world, bus)
    MatchSystem(world, bus)
    AnimationSystem(world, bus)
    MatchResolutionSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    BoardClearEffectSystem(world, bus)
    BoardTransformEffectSystem(world, bus)
    return bus, world, turn

def _activate_first_ability(bus, world):
    human_entities = list(world.get_component(HumanAgent))
    assert human_entities, 'No human agent found'
    owner_ent = human_entities[0][0]
    owner_comp = world.component_for_entity(owner_ent, AbilityListOwner)
    ability_ent = owner_comp.ability_entities[0]  # tactical_shift
    # Enter targeting; spend will occur after tile click (simulated)
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=ability_ent, owner_entity=owner_ent)
    return owner_ent, ability_ent


def _find_player_ability(world, ability_name: str) -> tuple[int, int]:
    for owner_ent, owner in world.get_component(AbilityListOwner):
        for ability_ent in owner.ability_entities:
            ability = world.component_for_entity(ability_ent, Ability)
            if ability.name == ability_name:
                return owner_ent, ability_ent
    raise AssertionError(f"Ability '{ability_name}' not found for any player")

def test_ability_without_match_rotates_turn(setup_world):
    bus, world, turn = setup_world
    # Ensure only the targeted tile changes type so no matches are formed.
    target_pos = (0, 0)
    _apply_board_pattern(world, {target_pos: 'nature'})
    owners = [ent for ent,_ in world.get_component(AbilityListOwner)]
    assert len(owners) >= 2
    initial_active = list(world.get_component(ActiveTurn))[0][1].owner_entity
    turn_events: list[dict] = []
    cascade_events: list[dict] = []
    bus.subscribe(EVENT_TURN_ADVANCED, lambda s, **k: turn_events.append(k))
    bus.subscribe(EVENT_CASCADE_COMPLETE, lambda s, **k: cascade_events.append(k))
    owner_ent, ability_ent = _activate_first_ability(bus, world)
    # Select target -> triggers spend request; simulate spend success afterwards
    bus.emit(EVENT_TILE_CLICK, row=target_pos[0], col=target_pos[1])
    ability = world.component_for_entity(ability_ent, Ability)
    bus.emit(EVENT_TILE_BANK_SPENT, entity=owner_ent, ability_entity=ability_ent, cost=ability.cost)
    assert cascade_events, 'Cascade completion should fire after ability resolution'
    assert len(cascade_events) == 1, f'Expected single cascade completion, saw {cascade_events}'
    assert turn_events, 'Turn should advance after ability resolution/cascade completion'
    assert len(turn_events) == 1, f'Expected single turn advance event, saw {turn_events}'
    last_event = turn_events[-1]
    assert last_event['new_owner'] != initial_active, 'TurnSystem reported no rotation'
    orders = list(world.get_component(TurnOrder))
    assert orders, 'TurnOrder component missing'
    order = orders[0][1]
    assert len(order.owners) >= 2, f'Turn order must list multiple owners, found {order.owners}'
    assert len(set(order.owners)) >= 2, f'Turn order owners are not unique: {order.owners}'
    active_components = list(world.get_component(ActiveTurn))
    assert len(active_components) == 1, 'Expected a single ActiveTurn component'
    new_active = active_components[0][1].owner_entity
    assert new_active != initial_active, 'Turn should advance after ability resolution/cascade completion'


def _drive_ticks(bus: EventBus, count: int = 600, dt: float = 1/60, *, until: list | None = None) -> None:
    emitted = 0
    while emitted < count:
        bus.emit(EVENT_TICK, dt=dt)
        emitted += 1
        if until is not None and until:
            break


def _apply_board_pattern(world, overrides: dict[tuple[int, int], str]):
    base = ['blood', 'secrets', 'spirit', 'witchfire']
    alt = ['secrets', 'spirit', 'witchfire', 'blood']
    for ent, pos in world.get_component(BoardPosition):
        tile = world.component_for_entity(ent, TileType)
        seq = base if (pos.row % 2 == 0) else alt
        tile.type_name = seq[pos.col % len(seq)]
    for (row, col), type_name in overrides.items():
        for ent, pos in world.get_component(BoardPosition):
            if pos.row == row and pos.col == col:
                tile = world.component_for_entity(ent, TileType)
                tile.type_name = type_name
                break


def test_tactical_shift_with_match_rotates_turn(setup_world):
    bus, world, _ = setup_world
    # Sculpt board so tactical shift creates a horizontal match on row 0 when converting nature -> hex.
    _apply_board_pattern(world, {
        (0, 0): 'hex',
        (0, 1): 'nature',
        (0, 2): 'hex',
    })
    initial_active = list(world.get_component(ActiveTurn))[0][1].owner_entity
    cascade_events: list[dict] = []
    cascade_steps: list[dict] = []
    match_found: list[dict] = []
    turn_events: list[dict] = []
    turn_actions: list[dict] = []
    bus.subscribe(EVENT_CASCADE_COMPLETE, lambda s, **k: cascade_events.append(k))
    bus.subscribe(EVENT_CASCADE_STEP, lambda s, **k: cascade_steps.append(k))
    bus.subscribe(EVENT_MATCH_FOUND, lambda s, **k: match_found.append(k))
    bus.subscribe(EVENT_TURN_ADVANCED, lambda s, **k: turn_events.append(k))
    bus.subscribe(EVENT_TURN_ACTION_STARTED, lambda s, **k: turn_actions.append(k))
    owner_ent, ability_ent = _activate_first_ability(bus, world)
    bus.emit(EVENT_TILE_CLICK, row=0, col=1)
    ability = world.component_for_entity(ability_ent, Ability)
    bus.emit(EVENT_TILE_BANK_SPENT, entity=owner_ent, ability_entity=ability_ent, cost=ability.cost)
    _drive_ticks(bus, until=cascade_events)
    state = list(world.get_component(TurnState))[0][1]
    states = list(world.get_component(TurnState))
    assert len(states) == 1, f'Expected single TurnState, found {len(states)}'
    assert match_found, 'Expected matches to be detected after tactical shift'
    assert cascade_steps, 'Expected cascade steps to run after tactical shift'
    assert cascade_events, f'Expected cascade completion after cascade-driven ability; turn_actions={turn_actions}, state_active={state.cascade_active}, state_depth={state.cascade_depth}, state_observed={state.cascade_observed}'
    assert any(event.get('depth', 0) >= 1 for event in cascade_events), f'Cascade depth should be >=1, got {cascade_events}'
    assert turn_events, 'Turn should advance once cascades resolve'
    assert turn_events[-1]['new_owner'] != initial_active
    assert len(turn_events) == 1, f'Turn advanced more than once: {turn_events}'


def test_free_ability_cascade_does_not_rotate_turn(setup_world):
    bus, world, _ = setup_world
    _apply_board_pattern(world, {
        (0, 0): 'hex',
        (0, 1): 'nature',
        (0, 2): 'hex',
    })
    initial_active = list(world.get_component(ActiveTurn))[0][1].owner_entity
    owner_ent, ability_ent = _find_player_ability(world, "tactical_shift")
    ability = world.component_for_entity(ability_ent, Ability)
    ability.ends_turn = False
    turn_events: list[dict] = []
    cascade_events: list[dict] = []
    bus.subscribe(EVENT_TURN_ADVANCED, lambda s, **k: turn_events.append(k))
    bus.subscribe(EVENT_CASCADE_COMPLETE, lambda s, **k: cascade_events.append(k))
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=ability_ent, owner_entity=owner_ent)
    bus.emit(EVENT_TILE_CLICK, row=0, col=1)
    bus.emit(EVENT_TILE_BANK_SPENT, entity=owner_ent, ability_entity=ability_ent, cost=ability.cost)
    _drive_ticks(bus, until=cascade_events)
    assert cascade_events, 'Expected cascade completion event after free tactical shift'
    assert not turn_events, f'Turn advanced despite free ability cascade: {turn_events}'
    active_components = list(world.get_component(ActiveTurn))
    assert len(active_components) == 1
    assert active_components[0][1].owner_entity == initial_active, 'Active turn should remain with original owner'
