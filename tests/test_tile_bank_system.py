from ecs.events.bus import EventBus, EVENT_MATCH_CLEARED, EVENT_TILE_BANK_SPEND_REQUEST, EVENT_TILE_BANK_SPENT, EVENT_TILE_BANK_INSUFFICIENT, EVENT_TILE_BANK_CHANGED
from ecs.world import create_world
from ecs.systems.tile_bank_system import TileBankSystem
from ecs.components.tile_bank import TileBank
from ecs.components.ability_list_owner import AbilityListOwner


def test_tile_bank_increments_on_match_clear():
    bus = EventBus(); world = create_world(bus)
    TileBankSystem(world, bus)
    owner_ent = list(world.get_component(AbilityListOwner))[0][0]
    # Simulate match cleared with semantic types
    types_payload = [(0,0,'archers'), (0,1,'archers'), (0,2,'cavalry')]
    changed = {}
    bus.subscribe(EVENT_TILE_BANK_CHANGED, lambda s, **k: changed.update(k))
    bus.emit(EVENT_MATCH_CLEARED, positions=[(0,0),(0,1),(0,2)], types=types_payload)
    assert changed.get('counts'), 'Tile bank not changed'
    counts = changed['counts']
    assert counts.get('archers') == 102  # prefilled 100 + 2
    assert counts.get('cavalry') == 101  # prefilled 100 + 1


def test_tile_bank_spend_success_and_failure():
    bus = EventBus(); world = create_world(bus)
    TileBankSystem(world, bus)
    owner_ent = list(world.get_component(AbilityListOwner))[0][0]
    # Pre-load bank via match clear (adds 2 archers, 1 cavalry)
    types_payload = [(0,0,'archers'), (0,1,'archers'), (0,2,'cavalry')]
    bus.emit(EVENT_MATCH_CLEARED, positions=[(0,0),(0,1),(0,2)], types=types_payload)
    spent = {}; insufficient = {}
    bus.subscribe(EVENT_TILE_BANK_SPENT, lambda s, **k: spent.update(k))
    bus.subscribe(EVENT_TILE_BANK_INSUFFICIENT, lambda s, **k: insufficient.update(k))
    # Spend valid cost
    bus.emit(EVENT_TILE_BANK_SPEND_REQUEST, entity=owner_ent, cost={'archers':2})
    assert spent.get('cost') == {'archers':2}
    # Spend invalid cost (insufficient cavalry) using exaggerated requirement
    bus.emit(EVENT_TILE_BANK_SPEND_REQUEST, entity=owner_ent, cost={'cavalry':200})
    assert insufficient.get('missing') == {'cavalry':99}
