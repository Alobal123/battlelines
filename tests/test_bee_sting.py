from ecs.events.bus import EventBus, EVENT_ABILITY_EXECUTE, EVENT_HEALTH_DAMAGE
from ecs.world import create_world
from ecs.components.ability import Ability
from ecs.components.ability_effect import AbilityEffects
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.health import Health
from ecs.components.human_agent import HumanAgent
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.tile import TileType
from ecs.factories.abilities import create_ability_by_name
from ecs.systems.ability_resolution_system import AbilityResolutionSystem
from ecs.systems.board import BoardSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.damage_effect_system import DamageEffectSystem
from ecs.systems.health_system import HealthSystem


def _human(world):
    return next(ent for ent, _ in world.get_component(HumanAgent))


def _enemy(world):
    return next(ent for ent, _ in world.get_component(RuleBasedAgent))


def _pending(ability_entity: int, owner_entity: int) -> PendingAbilityTarget:
    return PendingAbilityTarget(
        ability_entity=ability_entity,
        owner_entity=owner_entity,
        row=None,
        col=None,
        target_entity=owner_entity,
    )


def test_bee_sting_definition():
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)

    ability_entity = create_ability_by_name(world, "bee_sting")
    ability = world.component_for_entity(ability_entity, Ability)
    assert ability.cost == {"nature": 3, "spirit": 3, "shapeshift": 3}

    effects = world.component_for_entity(ability_entity, AbilityEffects)
    assert len(effects.effects) == 1
    spec = effects.effects[0]
    assert spec.slug == "damage"
    assert spec.metadata.get("reason") == "bee_sting"


def test_bee_sting_damage_equals_nature_tiles():
    bus = EventBus()
    world = create_world(bus)

    HealthSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    DamageEffectSystem(world, bus)
    AbilityResolutionSystem(world, bus)

    board_system = BoardSystem(world, bus, rows=2, cols=2)
    layout = [["nature", "nature"], ["nature", "hex"]]
    for row, row_values in enumerate(layout):
        for col, type_name in enumerate(row_values):
            entity = board_system._get_entity_at(row, col)
            assert entity is not None
            world.component_for_entity(entity, TileType).type_name = type_name

    human = _human(world)
    enemy = _enemy(world)

    owner_comp: AbilityListOwner = world.component_for_entity(enemy, AbilityListOwner)
    ability_entity = create_ability_by_name(world, "bee_sting")
    owner_comp.ability_entities.append(ability_entity)

    health_before = world.component_for_entity(human, Health).current

    damage_events = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda sender, **payload: damage_events.append(payload))

    bus.emit(
        EVENT_ABILITY_EXECUTE,
        ability_entity=ability_entity,
        owner_entity=enemy,
        pending=_pending(ability_entity, enemy),
    )

    assert damage_events, "Bee Sting should deal damage"
    payload = damage_events[-1]
    assert payload["target_entity"] == human
    assert payload["amount"] == 3
    assert payload.get("reason") == "bee_sting"

    health_after = world.component_for_entity(human, Health).current
    assert health_after == health_before - 3
