from ecs.events.bus import EventBus, EVENT_MATCH_CLEARED, EVENT_TILE_BANK_SPEND_REQUEST, EVENT_TILE_BANK_SPENT, EVENT_TILE_BANK_INSUFFICIENT, EVENT_TILE_BANK_CHANGED
from ecs.world import create_world
from ecs.systems.tile_bank_system import TileBankSystem
from ecs.components.tile_bank import TileBank
from ecs.components.ability_list_owner import AbilityListOwner


def test_tile_bank_increments_on_match_clear():
    bus = EventBus(); world = create_world(bus)
    TileBankSystem(world, bus)
    owner_ent = list(world.get_component(AbilityListOwner))[0][0]
    # Set up initial mana
    bank = world.component_for_entity(owner_ent, TileBank)
    bank.counts['hex'] = 100
    bank.counts['nature'] = 100
    # Use new faculty names
    types_payload = [(0,0,'hex'), (0,1,'hex'), (0,2,'nature')]
    changed = {}
    bus.subscribe(EVENT_TILE_BANK_CHANGED, lambda s, **k: changed.update(k))
    bus.emit(EVENT_MATCH_CLEARED, positions=[(0,0),(0,1),(0,2)], types=types_payload)
    assert changed.get('counts'), 'Tile bank not changed'
    counts = changed['counts']
    assert counts.get('hex') == 102  # initial 100 + 2
    assert counts.get('nature') == 101  # initial 100 + 1


def test_tile_bank_spend_success_and_failure():
    bus = EventBus(); world = create_world(bus)
    TileBankSystem(world, bus)
    owner_ent = list(world.get_component(AbilityListOwner))[0][0]
    # Pre-load bank via match clear (adds 2 hex, 1 nature)
    types_payload = [(0,0,'hex'), (0,1,'hex'), (0,2,'nature')]
    bus.emit(EVENT_MATCH_CLEARED, positions=[(0,0),(0,1),(0,2)], types=types_payload)
    spent = {}; insufficient = {}
    bus.subscribe(EVENT_TILE_BANK_SPENT, lambda s, **k: spent.update(k))
    bus.subscribe(EVENT_TILE_BANK_INSUFFICIENT, lambda s, **k: insufficient.update(k))
    # Spend valid cost
    bus.emit(EVENT_TILE_BANK_SPEND_REQUEST, entity=owner_ent, cost={'hex':2})
    assert spent.get('cost') == {'hex':2}
    # Spend invalid cost (insufficient nature) - bank has 1 nature, need 200
    bus.emit(EVENT_TILE_BANK_SPEND_REQUEST, entity=owner_ent, cost={'nature':200})
    # Missing should reflect available counts after prior increment (1 nature)
    assert insufficient.get('missing') == {'nature':199}


def test_no_regiment_readiness_side_effects():
    """Ensure readiness logic no longer mutates anything (placeholder)."""
    bus = EventBus(); world = create_world(bus)
    TileBankSystem(world, bus)
    owner_ent = list(world.get_component(AbilityListOwner))[0][0]
    # Emit a match clear with multiple types; should not raise or try to access removed components.
    types_payload = [(0,0,'hex'), (0,1,'hex'), (0,2,'hex')]
    bus.emit(EVENT_MATCH_CLEARED, positions=[(0,0),(0,1),(0,2)], types=types_payload, owner_entity=owner_ent)
    # Basic assertion: bank updated
    counts = None
    changed = {}
    bus.subscribe(EVENT_TILE_BANK_CHANGED, lambda s, **k: changed.update(k))
    bus.emit(EVENT_MATCH_CLEARED, positions=[(1,0),(1,1),(1,2)], types=types_payload, owner_entity=owner_ent)
    counts = changed.get('counts')
    # After two match clears of 3 hex each, should have 6 hex total
    assert counts and counts.get('hex') >= 6
