from ecs.events.bus import EventBus, EVENT_HEALTH_DAMAGE, EVENT_HEALTH_CHANGED, EVENT_MATCH_CLEARED, EVENT_EFFECT_APPLY
from ecs.world import create_world
from ecs.components.health import Health
from ecs.systems.health_system import HealthSystem
from ecs.systems.tile_bank_system import TileBankSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.damage_effect_system import DamageEffectSystem


def test_witchfire_damage_event_flow():
    """Verify witchfire clears emit damage events and HealthSystem applies them."""
    bus = EventBus()
    world = create_world(bus)
    health_system = HealthSystem(world, bus)
    effect_system = EffectLifecycleSystem(world, bus)
    damage_effect_system = DamageEffectSystem(world, bus)
    tile_bank_system = TileBankSystem(world, bus)
    
    # Find the two player entities with Health
    players = list(world.get_component(Health))
    assert len(players) >= 2, "Expected at least two players with Health"
    player1_ent, player1_hp = players[0]
    player2_ent, player2_hp = players[1]
    
    # Initial HP
    assert player1_hp.current == 30
    assert player2_hp.current == 30
    
    # Simulate witchfire cleared by player 1
    bus.emit(
        EVENT_MATCH_CLEARED,
        positions=[(0, 0), (0, 1), (0, 2)],
        types=[(0, 0, 'witchfire'), (0, 1, 'witchfire'), (0, 2, 'witchfire')],
        owner_entity=player1_ent,
    )
    
    # Player 2 should have taken 3 damage
    assert player2_hp.current == 27
    assert player1_hp.current == 30  # Player 1 unaffected


def test_damage_event_emits_health_changed():
    """Verify EVENT_HEALTH_CHANGED is emitted after damage application."""
    bus = EventBus()
    world = create_world(bus)
    health_system = HealthSystem(world, bus)
    effect_system = EffectLifecycleSystem(world, bus)
    damage_effect_system = DamageEffectSystem(world, bus)
    
    players = list(world.get_component(Health))
    target_ent, target_hp = players[0]
    
    health_changed_payload = {}
    def capture_health_changed(sender, **kwargs):
        health_changed_payload.update(kwargs)
    
    bus.subscribe(EVENT_HEALTH_CHANGED, capture_health_changed)
    
    # Emit damage via effect application
    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=target_ent,
        source_entity=None,
        slug="damage",
        turns=0,
        metadata={
            "amount": 5,
            "reason": "test",
            "source_owner": 999,
        },
    )
    
    assert target_hp.current == 25
    assert health_changed_payload.get('entity') == target_ent
    assert health_changed_payload.get('current') == 25
    assert health_changed_payload.get('delta') == -5
    assert health_changed_payload.get('reason') == 'test'
