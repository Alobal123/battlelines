import pytest
from ecs.events.bus import EventBus, EVENT_TILE_CLICK, EVENT_TILE_SWAP_REQUEST, EVENT_TILE_SWAP_DO, EVENT_MATCH_CLEARED
from ecs.world import create_world
from ecs.systems.board import BoardSystem
from ecs.systems.tile_bank_system import TileBankSystem
from ecs.systems.turn_system import TurnSystem
from ecs.components.tile_bank import TileBank
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.active_turn import ActiveTurn

class DummyEventCollector:
    def __init__(self):
        self.events = []
    def handler(self, sender, **payload):
        self.events.append(payload)

@pytest.fixture
def setup_world():
    bus = EventBus()
    world = create_world(bus)
    board = BoardSystem(world, bus)
    bank_sys = TileBankSystem(world, bus)
    TurnSystem(world, bus)
    return bus, world, board, bank_sys


def test_active_turn_changes_owner(setup_world):
    bus, world, board, bank_sys = setup_world
    owners = list(world.get_component(AbilityListOwner))
    assert len(owners) >= 2
    # Initial clicks set active turn to first owner (by current simplified logic)
    # ActiveTurn should be initialized by TurnSystem; verify owner
    active_list = list(world.get_component(ActiveTurn))
    assert active_list, 'ActiveTurn should be initialized'
    active_owner = active_list[0][1].owner_entity
    assert active_owner == owners[0][0]


def test_match_clear_attributed_to_active_owner(setup_world):
    bus, world, board, bank_sys = setup_world
    owners = list(world.get_component(AbilityListOwner))
    p1, p2 = owners[0][0], owners[1][0]
    # Force active turn to p2
    world.create_entity(ActiveTurn(owner_entity=p2))
    # Simulate a match cleared event with owner_entity=p2
    collector = DummyEventCollector()
    bus.subscribe(EVENT_MATCH_CLEARED, collector.handler)
    bus.emit(EVENT_MATCH_CLEARED, positions=[(0,0)], types=[(0,0,'ranged')], owner_entity=p2)
    # TileBankSystem should update p2 bank only
    p2_bank_ent = None
    for ent, bank in world.get_component(TileBank):
        if bank.owner_entity == p2:
            p2_bank_ent = ent
            break
    assert p2_bank_ent is not None
    p2_bank = world.component_for_entity(p2_bank_ent, TileBank)
    # Started prefilled at 100; after event should be 101
    assert p2_bank.counts.get('ranged', 0) == 101
    # Ensure p1 bank unchanged
    p1_bank_ent = None
    for ent, bank in world.get_component(TileBank):
        if bank.owner_entity == p1:
            p1_bank_ent = ent
            break
    p1_bank = world.component_for_entity(p1_bank_ent, TileBank)
    assert p1_bank.counts.get('ranged', 0) == 100
