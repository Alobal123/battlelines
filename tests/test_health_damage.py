from ecs.events.bus import (
    EventBus,
    EVENT_HEALTH_DAMAGE,
    EVENT_HEALTH_CHANGED,
    EVENT_MATCH_CLEARED,
    EVENT_TILES_MATCHED,
    EVENT_EFFECT_APPLY,
)
from world import create_world
from ecs.components.health import Health
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
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
    human_entities = list(world.get_component(HumanAgent))
    assert human_entities, "Expected a human-controlled player"
    player1_ent = human_entities[0][0]
    player1_hp = world.component_for_entity(player1_ent, Health)

    enemy_entities = list(world.get_component(RuleBasedAgent))
    assert enemy_entities, "Expected an enemy combatant"
    enemy_ent = enemy_entities[0][0]
    player2_hp = world.component_for_entity(enemy_ent, Health)
    
    # Initial HP snapshots
    player1_start = player1_hp.current
    player2_start = player2_hp.current
    assert player1_start == player1_hp.max_hp
    assert player2_start == player2_hp.max_hp
    
    # Simulate witchfire cleared by player 1
    bus.emit(
        EVENT_MATCH_CLEARED,
        positions=[(0, 0), (0, 1), (0, 2)],
        types=[(0, 0, 'witchfire'), (0, 1, 'witchfire'), (0, 2, 'witchfire')],
        owner_entity=player1_ent,
    )
    bus.emit(
        EVENT_TILES_MATCHED,
        positions=[(0, 0), (0, 1), (0, 2)],
        types=[(0, 0, 'witchfire'), (0, 1, 'witchfire'), (0, 2, 'witchfire')],
        owner_entity=player1_ent,
        source="test_witchfire",
    )
    
    # Player 2 should have taken 3 damage while the caster remains unchanged
    assert player2_hp.current == max(player2_start - 3, 0)
    assert player1_hp.current == player1_start  # Player 1 unaffected


def test_damage_event_emits_health_changed():
    """Verify EVENT_HEALTH_CHANGED is emitted after damage application."""
    bus = EventBus()
    world = create_world(bus)
    health_system = HealthSystem(world, bus)
    effect_system = EffectLifecycleSystem(world, bus)
    damage_effect_system = DamageEffectSystem(world, bus)
    
    human_entities = list(world.get_component(HumanAgent))
    assert human_entities, "Expected a human-controlled player"
    target_ent = human_entities[0][0]
    target_hp = world.component_for_entity(target_ent, Health)
    
    health_changed_payload = {}
    def capture_health_changed(sender, **kwargs):
        health_changed_payload.update(kwargs)
    
    bus.subscribe(EVENT_HEALTH_CHANGED, capture_health_changed)
    
    # Emit damage via effect application
    initial_hp = target_hp.current

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
    
    expected_hp = max(initial_hp - 5, 0)
    assert target_hp.current == expected_hp
    assert health_changed_payload.get('entity') == target_ent
    assert health_changed_payload.get('current') == expected_hp
    assert health_changed_payload.get('delta') == -5
    assert health_changed_payload.get('reason') == 'test'
