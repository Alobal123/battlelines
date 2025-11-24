import random
from typing import cast

from esper import World

from ecs.components.ability import Ability
from ecs.components.ability_cooldown import AbilityCooldown
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.ability_target import AbilityTarget
from ecs.components.active_switch import ActiveSwitch
from ecs.components.board import Board
from ecs.components.board_position import BoardPosition
from ecs.components.health import Health
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.tile import TileType
from ecs.components.tile_bank import TileBank
from ecs.events.bus import EventBus, EVENT_ABILITY_ACTIVATE_REQUEST, EVENT_TURN_ACTION_STARTED
from ecs.factories.abilities import create_ability_by_name
from ecs.systems.base_ai_system import AbilityAction, BaseAISystem
from ecs.systems.board_ops import find_valid_swaps
from ecs.ai.simulation import clone_world_state
from ecs.systems.rule_based_ai_system import RuleBasedAISystem
from world import create_world


def _build_board(world: World, layout: list[list[str]]) -> None:
    rows = len(layout)
    cols = len(layout[0]) if rows else 0
    world.create_entity(Board(rows=rows, cols=cols))
    for r, row in enumerate(layout):
        for c, type_name in enumerate(row):
            world.create_entity(
                BoardPosition(row=r, col=c),
                TileType(type_name=type_name),
                ActiveSwitch(active=True),
            )


def _get_ability_entity(world: World, owner: int, ability_name: str) -> int:
    owner_comp: AbilityListOwner = world.component_for_entity(owner, AbilityListOwner)
    for ability_entity in owner_comp.ability_entities:
        ability = world.component_for_entity(ability_entity, Ability)
        if ability.name == ability_name:
            return ability_entity
    ability_entity = create_ability_by_name(world, ability_name)
    owner_comp.ability_entities.append(ability_entity)
    return ability_entity


def test_rule_based_ai_prefers_lethal_ability_over_swap():
    bus = EventBus()
    world = create_world(bus)
    layout = [
        ["spirit", "nature", "hex"],
        ["blood", "hex", "secrets"],
        ["secrets", "hex", "blood"],
    ]
    _build_board(world, layout)
    ai_owner = next(ent for ent, _ in world.get_component(RuleBasedAgent))
    ability_entity = _get_ability_entity(world, ai_owner, "blood_bolt")
    owner_comp: AbilityListOwner = world.component_for_entity(ai_owner, AbilityListOwner)
    owner_comp.ability_entities = [ability_entity]
    # Give the AI enough mana to use blood_bolt
    bank = world.component_for_entity(ai_owner, TileBank)
    bank.counts["blood"] = 10
    # Set opponent low enough for blood_bolt to be lethal.
    opponent_entity = next(ent for ent, _ in world.get_component(Health) if ent != ai_owner)
    opponent_health: Health = world.component_for_entity(opponent_entity, Health)
    opponent_health.current = 5
    ai_system = RuleBasedAISystem(world, bus, rng=random.Random(0))

    # Ensure there is at least one valid swap candidate as an alternative option.
    assert find_valid_swaps(world), "Expected at least one swap candidate"

    action = ai_system._choose_action(ai_owner)
    assert action is not None
    kind, payload = action
    assert kind == "ability"
    ability_payload = cast(AbilityAction, payload)
    assert ability_payload.ability_entity == ability_entity


def test_rule_based_ai_prioritises_witchfire_targets():
    bus = EventBus()
    world = create_world(bus)
    layout = [
        ["witchfire", "nature", "hex", "blood"],
        ["nature", "hex", "blood", "hex"],
        ["spirit", "nature", "hex", "nature"],
        ["blood", "hex", "nature", "secrets"],
    ]
    _build_board(world, layout)
    ai_owner = next(ent for ent, _ in world.get_component(RuleBasedAgent))
    ability_entity = _get_ability_entity(world, ai_owner, "crimson_pulse")
    owner_comp: AbilityListOwner = world.component_for_entity(ai_owner, AbilityListOwner)
    owner_comp.ability_entities = [ability_entity]
    # Give the AI enough mana to use crimson_pulse
    bank = world.component_for_entity(ai_owner, TileBank)
    bank.counts["hex"] = 10
    ai_system = RuleBasedAISystem(world, bus, rng=random.Random(0))

    actions = ai_system._enumerate_ability_actions(ai_owner)
    witchfire_action = next(
        action
        for action in actions
        if action.ability_entity == ability_entity and action.target == (0, 0)
    )
    distant_action = next(
        action
        for action in actions
        if action.ability_entity == ability_entity and action.target == (3, 3)
    )

    score_witchfire = ai_system._score_action(ai_owner, ("ability", witchfire_action))
    score_distant = ai_system._score_action(ai_owner, ("ability", distant_action))

    assert score_witchfire > score_distant


def test_rule_based_ai_prefers_free_action_over_costlier_option():
    bus = EventBus()
    world = create_world(bus)
    ai_owner = next(ent for ent, _ in world.get_component(RuleBasedAgent))
    savagery_entity = _get_ability_entity(world, ai_owner, "savagery")
    blood_bolt_entity = _get_ability_entity(world, ai_owner, "blood_bolt")
    owner_comp: AbilityListOwner = world.component_for_entity(ai_owner, AbilityListOwner)
    owner_comp.ability_entities = [savagery_entity, blood_bolt_entity]
    # Give the AI enough mana for both abilities
    bank = world.component_for_entity(ai_owner, TileBank)
    bank.counts["shapeshift"] = 10
    bank.counts["blood"] = 10
    opponent_entity = next(ent for ent, _ in world.get_component(Health) if ent != ai_owner)
    opponent_health: Health = world.component_for_entity(opponent_entity, Health)
    opponent_health.current = 20
    ai_system = RuleBasedAISystem(world, bus, rng=random.Random(0))

    actions = ai_system._enumerate_ability_actions(ai_owner)
    savagery_action = next(
        action for action in actions if action.ability_entity == savagery_entity
    )
    blood_bolt_action = next(
        action for action in actions if action.ability_entity == blood_bolt_entity
    )

    score_savagery = ai_system._score_action(ai_owner, ("ability", savagery_action))
    score_blood_bolt = ai_system._score_action(ai_owner, ("ability", blood_bolt_action))

    assert score_savagery > score_blood_bolt


def test_rule_based_ai_detects_mana_gain_from_match():
    bus = EventBus()
    world = create_world(bus)
    layout = [
        ["nature", "blood", "nature"],
        ["hex", "nature", "hex"],
        ["blood", "hex", "blood"],
    ]
    _build_board(world, layout)
    ai_owner = next(ent for ent, _ in world.get_component(RuleBasedAgent))
    bank_entities = {ent for ent, _ in world.get_component(TileBank)}
    assert ai_owner in bank_entities
    bank: TileBank = world.component_for_entity(ai_owner, TileBank)
    for type_name in ["nature", "blood", "hex", "spirit", "shapeshift", "secrets"]:
        bank.counts[type_name] = 50

    ai_system = RuleBasedAISystem(world, bus, rng=random.Random(1))

    swap = ((0, 1), (1, 1))
    assert swap in find_valid_swaps(world)

    snapshot = ai_system._capture_owner_snapshot(ai_owner)
    clone_state = clone_world_state(world)
    clone_owner = clone_state.entity_map.get(ai_owner)
    assert clone_owner is not None

    from ecs.systems.board_ops import predict_swap_creates_match

    assert predict_swap_creates_match(clone_state.world, *swap)

    clone_state.engine.swap_and_resolve(*swap, acting_owner=clone_owner)

    clone_counts = ai_system._clone_bank_counts(clone_state.world, clone_owner)
    baseline_counts = snapshot.bank_counts
    clone_bank = clone_state.world.component_for_entity(clone_owner, TileBank)
    assert clone_bank.counts.get("nature", 0) > baseline_counts.get("nature", 0)
    baseline_deficits = ai_system._compute_mana_deficits(baseline_counts, snapshot.ability_map)
    other_gain, secrets_excess = ai_system._compute_bank_gains(
        baseline_counts,
        clone_counts,
        baseline_deficits,
    )

    assert other_gain >= 3
    assert secrets_excess == 0


class _TestFreeActionAI(BaseAISystem):
    def __init__(self, world: World, event_bus: EventBus, ability_entity: int):
        super().__init__(world, event_bus, RuleBasedAgent, rng=random.Random(0))
        self._ability_entity = ability_entity

    def _score_clone_world(self, clone_state, owner_entity, snapshot, candidate):
        return 0.0

    def _choose_action(self, owner_entity: int):  # type: ignore[override]
        return "ability", AbilityAction(
            ability_entity=self._ability_entity,
            target_type="self",
        )


def test_ai_requeues_after_free_ability_action():
    bus = EventBus()
    world = World()

    owner = world.create_entity(
        RuleBasedAgent(decision_delay=0.0, selection_delay=0.0),
        AbilityListOwner(ability_entities=[]),
        TileBank(owner_entity=0),
    )
    bank: TileBank = world.component_for_entity(owner, TileBank)
    bank.owner_entity = owner

    ability_entity = world.create_entity(
        Ability(name="test_scent", kind="active", cost={}, ends_turn=False),
        AbilityTarget(target_type="self", max_targets=0),
        AbilityCooldown(),
    )
    owner_comp: AbilityListOwner = world.component_for_entity(owner, AbilityListOwner)
    owner_comp.ability_entities = [ability_entity]

    def _handle_activate(sender, **payload):
        bus.emit(
            EVENT_TURN_ACTION_STARTED,
            source="ability",
            owner_entity=payload.get("owner_entity"),
            ability_entity=payload.get("ability_entity"),
        )

    bus.subscribe(EVENT_ABILITY_ACTIVATE_REQUEST, _handle_activate)

    ai_system = _TestFreeActionAI(world, bus, ability_entity)
    ai_system.pending_owner = owner
    ai_system.has_dispatched_action = False

    ai_system.on_tick(None, dt=0.0)

    assert ai_system.pending_owner == owner
    assert ai_system.has_dispatched_action is False
