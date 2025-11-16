import random

from ecs.events.bus import (
    EventBus,
    EVENT_EFFECT_APPLY,
    EVENT_TILE_BANK_CHANGED,
    EVENT_TILE_BANK_DEPLETED,
)
from ecs.world import create_world
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.tile_bank import TileBank
from ecs.components.effect_list import EffectList
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.deplete_effect_system import DepleteEffectSystem


def _find_human(world):
    return next(ent for ent, _ in world.get_component(HumanAgent))


def _find_enemy(world):
    return next(ent for ent, _ in world.get_component(RuleBasedAgent))


def test_deplete_specific_type_reduces_mana():
    bus = EventBus()
    world = create_world(bus)
    EffectLifecycleSystem(world, bus)
    DepleteEffectSystem(world, bus)

    player_ent = _find_human(world)
    enemy_ent = _find_enemy(world)

    enemy_bank: TileBank = world.component_for_entity(enemy_ent, TileBank)
    enemy_bank.counts.clear()
    enemy_bank.counts.update({"blood": 5, "spirit": 2})

    changed_events = []
    depleted_events = []
    bus.subscribe(EVENT_TILE_BANK_CHANGED, lambda sender, **payload: changed_events.append(payload))
    bus.subscribe(EVENT_TILE_BANK_DEPLETED, lambda sender, **payload: depleted_events.append(payload))

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=enemy_ent,
        slug="deplete",
        turns=0,
        metadata={
            "amount": 3,
            "mode": "type",
            "type_name": "blood",
            "reason": "siphon",
            "source_owner": player_ent,
        },
    )

    assert enemy_bank.counts["blood"] == 2
    assert enemy_bank.counts["spirit"] == 2
    assert changed_events, "Deplete effect did not emit tile bank change"
    assert depleted_events, "Deplete effect did not emit depletion event"
    last_depleted = depleted_events[-1]
    assert last_depleted["owner_entity"] == enemy_ent
    assert last_depleted["source_owner"] == player_ent
    assert last_depleted["deltas"] == {"blood": 3}
    effect_list: EffectList = world.component_for_entity(enemy_ent, EffectList)
    assert effect_list.effect_entities == []


def test_deplete_unsupported_mode_noop():
    bus = EventBus()
    world = create_world(bus)
    EffectLifecycleSystem(world, bus)
    DepleteEffectSystem(world, bus)

    enemy_ent = _find_enemy(world)
    enemy_bank: TileBank = world.component_for_entity(enemy_ent, TileBank)
    enemy_bank.counts.clear()
    enemy_bank.counts.update({"blood": 4})

    changed_events = []
    depleted_events = []
    bus.subscribe(EVENT_TILE_BANK_CHANGED, lambda sender, **payload: changed_events.append(payload))
    bus.subscribe(EVENT_TILE_BANK_DEPLETED, lambda sender, **payload: depleted_events.append(payload))

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=enemy_ent,
        slug="deplete",
        turns=0,
        metadata={
            "amount": 2,
            "mode": "max",
        },
    )

    assert enemy_bank.counts["blood"] == 4
    assert not changed_events
    assert not depleted_events
    effect_list: EffectList = world.component_for_entity(enemy_ent, EffectList)
    assert effect_list.effect_entities == []


def test_deplete_all_mode_reduces_each_type():
    bus = EventBus()
    world = create_world(bus)
    EffectLifecycleSystem(world, bus)
    DepleteEffectSystem(world, bus)

    enemy_ent = _find_enemy(world)
    enemy_bank: TileBank = world.component_for_entity(enemy_ent, TileBank)
    enemy_bank.counts.clear()
    enemy_bank.counts.update({"blood": 4, "spirit": 1, "hex": 0})

    changed_events = []
    depleted_events = []
    bus.subscribe(EVENT_TILE_BANK_CHANGED, lambda sender, **payload: changed_events.append(payload))
    bus.subscribe(EVENT_TILE_BANK_DEPLETED, lambda sender, **payload: depleted_events.append(payload))

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=enemy_ent,
        slug="deplete",
        turns=0,
        metadata={
            "amount": 2,
            "mode": "all",
        },
    )

    assert enemy_bank.counts["blood"] == 2
    assert enemy_bank.counts["spirit"] == 0
    assert enemy_bank.counts["hex"] == 0
    assert changed_events, "All-mode deplete should update bank counts"
    assert depleted_events, "All-mode deplete should emit depletion event"
    event = depleted_events[-1]
    assert event["deltas"] == {"blood": 2, "spirit": 1}
    assert event["mode"] == "all"
    effect_list = world.component_for_entity(enemy_ent, EffectList)
    assert effect_list.effect_entities == []


def test_deplete_random_mode_drains_single_type():
    random.seed(0)
    bus = EventBus()
    world = create_world(bus)
    EffectLifecycleSystem(world, bus)
    DepleteEffectSystem(world, bus)

    enemy_ent = _find_enemy(world)
    enemy_bank: TileBank = world.component_for_entity(enemy_ent, TileBank)
    enemy_bank.counts.clear()
    enemy_bank.counts.update({"blood": 4, "spirit": 5, "hex": 1})

    changed_events = []
    depleted_events = []
    bus.subscribe(EVENT_TILE_BANK_CHANGED, lambda sender, **payload: changed_events.append(payload))
    bus.subscribe(EVENT_TILE_BANK_DEPLETED, lambda sender, **payload: depleted_events.append(payload))

    bus.emit(
        EVENT_EFFECT_APPLY,
        owner_entity=enemy_ent,
        slug="deplete",
        turns=0,
        metadata={
            "amount": 2,
            "mode": "random_eligible",
        },
    )

    assert changed_events, "Random mode should emit a bank change"
    assert depleted_events, "Random mode should emit a depletion event"
    deltas = depleted_events[-1]["deltas"]
    assert sum(deltas.values()) == 2
    assert len(deltas) == 1, "Random mode should affect only one type"
    affected_type = next(iter(deltas))
    assert enemy_bank.counts[affected_type] == (
        {"blood": 4, "spirit": 5, "hex": 1}[affected_type] - 2
    )
    assert depleted_events[-1]["mode"] == "random_eligible"
    effect_list = world.component_for_entity(enemy_ent, EffectList)
    assert effect_list.effect_entities == []
