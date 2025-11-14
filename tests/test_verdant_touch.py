from ecs.events.bus import EventBus, EVENT_HEALTH_HEAL, EVENT_HEALTH_CHANGED, EVENT_ABILITY_EFFECT_APPLIED
from ecs.world import create_world
from ecs.components.health import Health
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.ability import Ability
from ecs.systems.health_system import HealthSystem
from ecs.systems.ability_resolution_system import AbilityResolutionSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.heal_effect_system import HealEffectSystem
from ecs.components.pending_ability_target import PendingAbilityTarget


def test_verdant_touch_heals_caster():
    """Verdant Touch should heal the casting player by 4 HP."""
    bus = EventBus()
    world = create_world(bus)
    
    # Wire up health system to handle healing events
    health_system = HealthSystem(world, bus)
    effect_system = EffectLifecycleSystem(world, bus)
    heal_effect_system = HealEffectSystem(world, bus)
    resolution_system = AbilityResolutionSystem(world, bus)
    
    # Find player 1 and their verdant_touch ability
    player_entities = [ent for ent in world.get_component(AbilityListOwner)]
    assert len(player_entities) >= 1, "Expected at least one player"
    player1 = player_entities[0][0]
    
    # Get player's abilities
    ability_owner = world.component_for_entity(player1, AbilityListOwner)
    verdant_abilities = [
        ent for ent in ability_owner.ability_entities
        if world.component_for_entity(ent, Ability).name == "verdant_touch"
    ]
    assert len(verdant_abilities) == 1, "Expected player to have verdant_touch ability"
    verdant_entity = verdant_abilities[0]
    
    # Damage player first so we can see healing
    health = world.component_for_entity(player1, Health)
    health.current = 20  # Down from 30
    
    # Track events
    heal_events = []
    changed_events = []
    effect_events = []
    
    bus.subscribe(EVENT_HEALTH_HEAL, lambda s, **k: heal_events.append(k))
    bus.subscribe(EVENT_HEALTH_CHANGED, lambda s, **k: changed_events.append(k))
    bus.subscribe(EVENT_ABILITY_EFFECT_APPLIED, lambda s, **k: effect_events.append(k))
    
    # Create pending target (verdant touch doesn't need a tile target)
    pending = PendingAbilityTarget(
        ability_entity=verdant_entity,
        owner_entity=player1,
        row=None,
        col=None,
        target_entity=None,
    )
    
    # Emit ability execute event
    from ecs.events.bus import EVENT_ABILITY_EXECUTE
    bus.emit(EVENT_ABILITY_EXECUTE, ability_entity=verdant_entity, owner_entity=player1, pending=pending)
    
    # Verify healing event was emitted
    assert len(heal_events) == 1, "Expected one heal event"
    assert heal_events[0]["target_entity"] == player1
    assert heal_events[0]["amount"] == 4
    assert heal_events[0]["reason"] == "verdant_touch"
    
    # Verify health changed event
    assert len(changed_events) == 1, "Expected one health changed event"
    assert changed_events[0]["entity"] == player1
    assert changed_events[0]["current"] == 24  # 20 + 4
    assert changed_events[0]["delta"] == 4
    
    # Verify health component was updated
    assert health.current == 24


def test_verdant_touch_caps_at_max_hp():
    """Healing should not exceed max HP."""
    bus = EventBus()
    world = create_world(bus)
    
    health_system = HealthSystem(world, bus)
    effect_system = EffectLifecycleSystem(world, bus)
    heal_effect_system = HealEffectSystem(world, bus)
    resolution_system = AbilityResolutionSystem(world, bus)
    
    # Find player 1
    player_entities = [ent for ent in world.get_component(AbilityListOwner)]
    player1 = player_entities[0][0]
    
    # Get verdant_touch ability
    ability_owner = world.component_for_entity(player1, AbilityListOwner)
    verdant_entity = [
        ent for ent in ability_owner.ability_entities
        if world.component_for_entity(ent, Ability).name == "verdant_touch"
    ][0]
    
    # Player at 28 HP (max 30)
    health = world.component_for_entity(player1, Health)
    health.current = 28
    
    changed_events = []
    bus.subscribe(EVENT_HEALTH_CHANGED, lambda s, **k: changed_events.append(k))
    
    # Execute ability
    pending = PendingAbilityTarget(
        ability_entity=verdant_entity,
        owner_entity=player1,
        row=None,
        col=None,
        target_entity=None,
    )
    
    from ecs.events.bus import EVENT_ABILITY_EXECUTE
    bus.emit(EVENT_ABILITY_EXECUTE, ability_entity=verdant_entity, owner_entity=player1, pending=pending)
    
    # Verify healing was capped
    assert health.current == 30, "HP should be capped at max_hp"
    assert changed_events[0]["delta"] == 2, "Delta should reflect actual change (2, not 4)"
