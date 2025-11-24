from ecs.events.bus import EventBus, EVENT_HEALTH_HEAL, EVENT_HEALTH_CHANGED, EVENT_ABILITY_EFFECT_APPLIED
from world import create_world
from ecs.components.health import Health
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.ability import Ability
from ecs.components.human_agent import HumanAgent
from ecs.systems.health_system import HealthSystem
from ecs.systems.ability_resolution_system import AbilityResolutionSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.heal_effect_system import HealEffectSystem
from ecs.components.pending_ability_target import PendingAbilityTarget

from tests.helpers import grant_player_abilities


def test_verdant_touch_heals_caster():
    """Verdant Touch should heal the casting player by 4 HP."""
    bus = EventBus()
    world = create_world(bus)
    grant_player_abilities(world, ("verdant_touch",))
    
    # Wire up health system to handle healing events
    health_system = HealthSystem(world, bus)
    effect_system = EffectLifecycleSystem(world, bus)
    heal_effect_system = HealEffectSystem(world, bus)
    resolution_system = AbilityResolutionSystem(world, bus)
    
    # Find player 1 and their verdant_touch ability
    human_entities = list(world.get_component(HumanAgent))
    assert human_entities, "Expected at least one player"
    player1 = human_entities[0][0]
    
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
    max_hp = health.max_hp
    heal_amount = 4
    start_hp = max(0, max_hp - (heal_amount + 1))
    health.current = start_hp
    
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
    expected_hp = min(max_hp, start_hp + heal_amount)
    assert changed_events[0]["current"] == expected_hp
    assert changed_events[0]["delta"] == expected_hp - start_hp
    
    # Verify health component was updated
    assert health.current == expected_hp


def test_verdant_touch_caps_at_max_hp():
    """Healing should not exceed max HP."""
    bus = EventBus()
    world = create_world(bus)
    grant_player_abilities(world, ("verdant_touch",))
    
    health_system = HealthSystem(world, bus)
    effect_system = EffectLifecycleSystem(world, bus)
    heal_effect_system = HealEffectSystem(world, bus)
    resolution_system = AbilityResolutionSystem(world, bus)
    
    # Find player 1
    human_entities = list(world.get_component(HumanAgent))
    assert human_entities, "Expected at least one player"
    player1 = human_entities[0][0]
    
    # Get verdant_touch ability
    ability_owner = world.component_for_entity(player1, AbilityListOwner)
    verdant_entity = [
        ent for ent in ability_owner.ability_entities
        if world.component_for_entity(ent, Ability).name == "verdant_touch"
    ][0]
    
    # Player just below max to test capping behaviour
    health = world.component_for_entity(player1, Health)
    max_hp = health.max_hp
    heal_amount = 4
    missing = min(2, max_hp)
    health.current = max_hp - missing
    
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
    assert health.current == max_hp, "HP should be capped at max_hp"
    expected_delta = min(heal_amount, missing)
    assert changed_events[0]["delta"] == expected_delta, "Delta should reflect actual change"
