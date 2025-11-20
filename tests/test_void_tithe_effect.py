from esper import World

from ecs.events.bus import (
    EventBus,
    EVENT_EFFECT_APPLY,
    EVENT_HEALTH_DAMAGE,
    EVENT_TURN_ADVANCED,
)
from ecs.world import create_world
from ecs.components.health import Health
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.board_position import BoardPosition
from ecs.components.active_switch import ActiveSwitch
from ecs.systems.board import BoardSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.damage_effect_system import DamageEffectSystem
from ecs.systems.effects.void_tithe_effect_system import VoidTitheEffectSystem
from ecs.systems.health_system import HealthSystem


def _setup_systems(world: World, bus: EventBus) -> None:
    BoardSystem(world, bus, rows=3, cols=3)
    HealthSystem(world, bus)
    EffectLifecycleSystem(world, bus)
    DamageEffectSystem(world, bus)
    VoidTitheEffectSystem(world, bus)


def _players(world: World) -> tuple[int, int]:
    owner = next(entity for entity, _ in world.get_component(HumanAgent))
    opponent = next(entity for entity, _ in world.get_component(RuleBasedAgent))
    return owner, opponent


def _set_inactive_tiles(world: World, count: int) -> None:
    remaining = count
    for entity, _ in world.get_component(BoardPosition):
        if remaining <= 0:
            break
        try:
            switch: ActiveSwitch = world.component_for_entity(entity, ActiveSwitch)
        except KeyError:
            continue
        switch.active = False
        remaining -= 1


def test_void_tithe_deals_damage_equal_to_missing_tiles() -> None:
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    _setup_systems(world, bus)

    owner, opponent = _players(world)

    _set_inactive_tiles(world, 4)

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=owner,
        source_entity=None,
        slug="void_tithe",
        turns=None,
    )

    damage_events: list[dict] = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda s, **k: damage_events.append(k))

    enemy_health: Health = world.component_for_entity(opponent, Health)
    starting_hp = enemy_health.current

    bus.emit(EVENT_TURN_ADVANCED, previous_owner=owner)

    assert damage_events
    event = damage_events[0]
    assert event.get("target_entity") == opponent
    assert event.get("amount") == 4
    assert event.get("reason") == "void_tithe"

    assert enemy_health.current == starting_hp - 4


def test_void_tithe_no_damage_without_missing_tiles() -> None:
    bus = EventBus()
    world = create_world(bus, grant_default_player_abilities=False)
    _setup_systems(world, bus)

    owner, opponent = _players(world)

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=owner,
        source_entity=None,
        slug="void_tithe",
        turns=None,
    )

    damage_events: list[dict] = []
    bus.subscribe(EVENT_HEALTH_DAMAGE, lambda s, **k: damage_events.append(k))

    bus.emit(EVENT_TURN_ADVANCED, previous_owner=owner)

    assert not damage_events

    # Ensure opponent damage still absent even if event references other owner
    bus.emit(EVENT_TURN_ADVANCED, previous_owner=opponent)
    assert not damage_events
