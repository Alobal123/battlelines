from ecs.events.bus import EventBus, EVENT_MATCH_CLEARED, EVENT_TILE_BANK_SPEND_REQUEST, EVENT_TILE_BANK_SPENT, EVENT_TILE_BANK_INSUFFICIENT, EVENT_TILE_BANK_CHANGED
from ecs.world import create_world
from ecs.systems.tile_bank_system import TileBankSystem
from ecs.components.tile_bank import TileBank
from ecs.components.ability_list_owner import AbilityListOwner


def test_tile_bank_increments_on_match_clear():
    bus = EventBus(); world = create_world(bus)
    TileBankSystem(world, bus)
    owner_ent = list(world.get_component(AbilityListOwner))[0][0]
    # Simulate match cleared with two colors
    colors_payload = [(0,0,(10,10,10)), (0,1,(10,10,10)), (0,2,(20,20,20))]
    changed = {}
    bus.subscribe(EVENT_TILE_BANK_CHANGED, lambda s, **k: changed.update(k))
    bus.emit(EVENT_MATCH_CLEARED, positions=[(0,0),(0,1),(0,2)], colors=colors_payload)
    assert changed.get('counts'), 'Tile bank not changed'
    counts = changed['counts']
    assert counts.get('10_10_10') == 2
    assert counts.get('20_20_20') == 1


def test_tile_bank_spend_success_and_failure():
    bus = EventBus(); world = create_world(bus)
    TileBankSystem(world, bus)
    owner_ent = list(world.get_component(AbilityListOwner))[0][0]
    # Pre-load bank via match clear
    colors_payload = [(0,0,(10,10,10)), (0,1,(10,10,10)), (0,2,(20,20,20))]
    bus.emit(EVENT_MATCH_CLEARED, positions=[(0,0),(0,1),(0,2)], colors=colors_payload)
    spent = {}; insufficient = {}
    bus.subscribe(EVENT_TILE_BANK_SPENT, lambda s, **k: spent.update(k))
    bus.subscribe(EVENT_TILE_BANK_INSUFFICIENT, lambda s, **k: insufficient.update(k))
    # Spend valid cost
    bus.emit(EVENT_TILE_BANK_SPEND_REQUEST, entity=owner_ent, cost={'10_10_10':2})
    assert spent.get('cost') == {'10_10_10':2}
    # Spend invalid cost (insufficient)
    bus.emit(EVENT_TILE_BANK_SPEND_REQUEST, entity=owner_ent, cost={'20_20_20':2})
    assert insufficient.get('missing') == {'20_20_20':1}
