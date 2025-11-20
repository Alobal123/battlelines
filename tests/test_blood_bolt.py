from ecs.events.bus import EventBus, EVENT_HEALTH_DAMAGE, EVENT_HEALTH_CHANGED, EVENT_ABILITY_EFFECT_APPLIED, EVENT_EFFECT_APPLY
from ecs.world import create_world
from ecs.components.health import Health
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.ability import Ability
from ecs.components.ability_effect import AbilityEffects
from ecs.systems.health_system import HealthSystem
from ecs.systems.ability_resolution_system import AbilityResolutionSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.damage_effect_system import DamageEffectSystem
from ecs.components.pending_ability_target import PendingAbilityTarget


def test_blood_bolt_damages_both_players():
    """Blood Bolt should damage both the caster and opponent."""
    bus = EventBus()
    world = create_world(bus)
    
    # Wire up health system to handle damage events
    health_system = HealthSystem(world, bus)
    effect_system = EffectLifecycleSystem(world, bus)
    damage_effect_system = DamageEffectSystem(world, bus)
    resolution_system = AbilityResolutionSystem(world, bus)
    
    # Find both players
    player_entities = sorted([ent for ent in world.get_component(AbilityListOwner)], key=lambda p: p[0])
    assert len(player_entities) >= 2, "Expected at least two players"
    player1 = player_entities[0][0]
    player2 = player_entities[1][0]
    
    # Get player1's blood_bolt ability
    ability_owner = world.component_for_entity(player1, AbilityListOwner)
    bolt_abilities = [
        ent for ent in ability_owner.ability_entities
        if world.component_for_entity(ent, Ability).name == "blood_bolt"
    ]
    assert len(bolt_abilities) == 1, "Expected player to have blood_bolt ability"
    bolt_entity = bolt_abilities[0]
    bolt_ability = world.component_for_entity(bolt_entity, Ability)
    self_damage_expected = bolt_ability.params.get("self_damage")
    opponent_damage_expected = bolt_ability.params.get("opponent_damage")
    if self_damage_expected is None or opponent_damage_expected is None:
        effects = world.component_for_entity(bolt_entity, AbilityEffects)
        for spec in effects.effects:
            if spec.target == "self" and spec.metadata.get("amount") is not None:
                self_damage_expected = int(spec.metadata["amount"])
            if spec.target == "opponent" and spec.metadata.get("amount") is not None:
                opponent_damage_expected = int(spec.metadata["amount"])
    
    # Track damage events
    damage_events = []
    changed_events = []
    
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda s, **k: damage_events.append(k))
    bus.subscribe(EVENT_HEALTH_CHANGED, lambda s, **k: changed_events.append(k))
    
    # Get initial HP
    health1 = world.component_for_entity(player1, Health)
    health2 = world.component_for_entity(player2, Health)
    initial_hp1 = health1.current
    initial_hp2 = health2.current
    
    # Create pending target (blood bolt doesn't need a tile target)
    pending = PendingAbilityTarget(
        ability_entity=bolt_entity,
        owner_entity=player1,
        row=None,
        col=None,
        target_entity=player1,  # Self-targeting
    )
    
    # Emit ability execute event
    from ecs.events.bus import EVENT_ABILITY_EXECUTE
    bus.emit(EVENT_ABILITY_EXECUTE, ability_entity=bolt_entity, owner_entity=player1, pending=pending)
    
    # Verify two damage events were emitted
    assert len(damage_events) == 2, f"Expected two damage events, got {len(damage_events)}"
    
    # Verify self-damage event
    self_damage = [e for e in damage_events if e.get("reason") == "blood_bolt_self"]
    assert len(self_damage) == 1, "Expected one self-damage event"
    assert self_damage[0]["target_entity"] == player1
    assert self_damage_expected is not None
    assert self_damage[0]["amount"] == self_damage_expected
    assert self_damage[0]["source_owner"] == player1
    
    # Verify opponent damage event
    opponent_damage = [e for e in damage_events if e.get("reason") == "blood_bolt"]
    assert len(opponent_damage) == 1, "Expected one opponent damage event"
    assert opponent_damage[0]["target_entity"] == player2
    assert opponent_damage_expected is not None
    assert opponent_damage[0]["amount"] == opponent_damage_expected
    assert opponent_damage[0]["source_owner"] == player1
    
    # Verify health was updated correctly
    assert health1.current == initial_hp1 - self_damage_expected, (
        f"Player 1 should take {self_damage_expected} damage, HP: {health1.current}"
    )
    assert health2.current == initial_hp2 - opponent_damage_expected, (
        f"Player 2 should take {opponent_damage_expected} damage, HP: {health2.current}"
    )
    
    # Verify two health changed events
    assert len(changed_events) == 2, f"Expected two health changed events, got {len(changed_events)}"


def test_blood_bolt_reason_distinguishable_from_witchfire():
    """Blood Bolt damage should have distinct reason from witchfire damage."""
    bus = EventBus()
    world = create_world(bus)
    
    health_system = HealthSystem(world, bus)
    effect_system = EffectLifecycleSystem(world, bus)
    damage_effect_system = DamageEffectSystem(world, bus)
    
    # Track all damage events
    damage_events = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda s, **k: damage_events.append(k))
    
    # Get a player entity
    player_entities = [ent for ent in world.get_component(AbilityListOwner)]
    player1 = player_entities[0][0]
    
    # Simulate blood_bolt damage via effect
    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=player1,
        source_entity=None,
        slug="damage",
        turns=0,
        metadata={
            "amount": 2,
            "reason": "blood_bolt_self",
            "source_owner": player1,
        },
    )
    
    # Simulate witchfire damage via effect
    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=player1,
        source_entity=None,
        slug="damage",
        turns=0,
        metadata={
            "amount": 3,
            "reason": "witchfire",
            "source_owner": player1,
        },
    )
    
    # Verify we can distinguish between damage types
    assert len(damage_events) == 2
    
    blood_bolt_damage = [e for e in damage_events if e["reason"] == "blood_bolt_self"]
    witchfire_damage = [e for e in damage_events if e["reason"] == "witchfire"]
    
    assert len(blood_bolt_damage) == 1, "Should have one blood_bolt_self damage"
    assert len(witchfire_damage) == 1, "Should have one witchfire damage"
    
    # Verify reasons are different
    assert blood_bolt_damage[0]["reason"] != witchfire_damage[0]["reason"]
    assert blood_bolt_damage[0]["amount"] == 2
    assert witchfire_damage[0]["amount"] == 3


def test_blood_bolt_opponent_damage_has_correct_reason():
    """Opponent damage from Blood Bolt should have 'blood_bolt' reason."""
    bus = EventBus()
    world = create_world(bus)
    
    health_system = HealthSystem(world, bus)
    effect_system = EffectLifecycleSystem(world, bus)
    damage_effect_system = DamageEffectSystem(world, bus)
    resolution_system = AbilityResolutionSystem(world, bus)
    
    player_entities = sorted([ent for ent in world.get_component(AbilityListOwner)], key=lambda p: p[0])
    player1 = player_entities[0][0]
    
    ability_owner = world.component_for_entity(player1, AbilityListOwner)
    bolt_entity = [
        ent for ent in ability_owner.ability_entities
        if world.component_for_entity(ent, Ability).name == "blood_bolt"
    ][0]
    
    damage_events = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda s, **k: damage_events.append(k))
    
    pending = PendingAbilityTarget(
        ability_entity=bolt_entity,
        owner_entity=player1,
        row=None,
        col=None,
        target_entity=player1,
    )
    
    from ecs.events.bus import EVENT_ABILITY_EXECUTE
    bus.emit(EVENT_ABILITY_EXECUTE, ability_entity=bolt_entity, owner_entity=player1, pending=pending)
    
    # Check both damage reasons are present and correct
    reasons = [e["reason"] for e in damage_events]
    assert "blood_bolt_self" in reasons, "Should have blood_bolt_self damage"
    assert "blood_bolt" in reasons, "Should have blood_bolt (opponent) damage"
    assert "witchfire" not in reasons, "Should not have witchfire damage"
