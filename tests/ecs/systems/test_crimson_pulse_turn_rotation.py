import pytest
from ecs.events.bus import EventBus, EVENT_ABILITY_ACTIVATE_REQUEST, EVENT_TILE_CLICK, EVENT_TILE_BANK_SPENT, EVENT_TURN_ADVANCED, EVENT_CASCADE_COMPLETE, EVENT_CASCADE_STEP, EVENT_TICK
from ecs.world import create_world
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.ability_targeting_system import AbilityTargetingSystem
from ecs.systems.tile_bank_system import TileBankSystem
from ecs.systems.turn_system import TurnSystem
from ecs.systems.board import BoardSystem
from ecs.systems.match import MatchSystem
from ecs.systems.match_resolution import MatchResolutionSystem
from ecs.systems.animation import AnimationSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.board_clear_effect_system import BoardClearEffectSystem
from ecs.systems.effects.board_transform_effect_system import BoardTransformEffectSystem
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.active_turn import ActiveTurn

@pytest.fixture
def setup_world():
    bus = EventBus(); world = create_world(bus)
    AbilityTargetingSystem(world, bus)
    AbilitySystem(world, bus)
    TileBankSystem(world, bus)
    TurnSystem(world, bus)
    BoardSystem(world, bus)
    MatchSystem(world, bus)
    AnimationSystem(world, bus)
    MatchResolutionSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    BoardClearEffectSystem(world, bus)
    BoardTransformEffectSystem(world, bus)
    return bus, world

def _activate_crimson_pulse(bus, world):
    owners = list(world.get_component(AbilityListOwner))
    owner_ent, owner_comp = owners[0]
    # Give the owner enough mana to use crimson_pulse (costs 5 hex)
    from ecs.components.tile_bank import TileBank
    bank = world.component_for_entity(owner_ent, TileBank)
    bank.counts["hex"] = 10
    from ecs.components.ability import Ability
    ability_ent = None
    for ent, ability in world.get_component(Ability):
        if ability.name == 'crimson_pulse' and ent in owner_comp.ability_entities:
            ability_ent = ent
            break
    assert ability_ent is not None, 'crimson_pulse ability not found'
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=ability_ent, owner_entity=owner_ent)
    # Click target (0,0)
    bus.emit(EVENT_TILE_CLICK, row=0, col=0)
    # Spend cost success
    ability = world.component_for_entity(ability_ent, Ability)
    bus.emit(EVENT_TILE_BANK_SPENT, entity=owner_ent, ability_entity=ability_ent, cost=ability.cost)
    return owner_ent, ability_ent


def _drive_ticks(bus: EventBus, count: int = 90, dt: float = 1/60) -> None:
    for _ in range(count):
        bus.emit(EVENT_TICK, dt=dt)

def test_crimson_pulse_turn_advances_via_depth_zero_cascade_complete(setup_world):
    bus, world = setup_world
    active_before = list(world.get_component(ActiveTurn))[0][1].owner_entity
    events = []
    cascade_events = []
    bus.subscribe(EVENT_CASCADE_COMPLETE, lambda s, **k: cascade_events.append(k))
    bus.subscribe(EVENT_TURN_ADVANCED, lambda s, **k: events.append(k))
    _activate_crimson_pulse(bus, world)
    _drive_ticks(bus)
    assert events, 'Turn should advance after ability resolution'
    assert cascade_events, 'Expected cascade_complete event'
    assert events[-1]['previous_owner'] == active_before
