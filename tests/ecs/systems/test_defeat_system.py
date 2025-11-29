import pytest

from ecs.events.bus import (
    EventBus,
    EVENT_CHOICE_SELECTED,
    EVENT_COMBAT_RESET,
    EVENT_ENTITY_DEFEATED,
    EVENT_PLAYER_DEFEATED,
)
from world import create_world
from ecs.systems.defeat_system import DefeatSystem
from ecs.components.game_over_choice import GameOverChoice
from ecs.components.choice_window import ChoiceOption, ChoiceWindow
from ecs.components.game_state import GameMode, GameState
from ecs.components.human_agent import HumanAgent
from ecs.components.rule_based_agent import RuleBasedAgent
from ecs.components.tile_bank import TileBank
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.ability_cooldown import AbilityCooldown
from ecs.components.pending_ability_target import PendingAbilityTarget
from ecs.components.targeting_state import TargetingState
from ecs.components.effect_list import EffectList
from ecs.components.effect import Effect
from ecs.components.health import Health
from ecs.components.turn_order import TurnOrder
from ecs.components.active_turn import ActiveTurn
from ecs.menu.components import MenuButton
from ecs.systems.board import BoardSystem
from ecs.systems.board_ops import find_all_matches

from tests.helpers import grant_player_abilities


def _human_entity(world):
    return next(ent for ent, _ in world.get_component(HumanAgent))


def _enemy_entity(world):
    return next(ent for ent, _ in world.get_component(RuleBasedAgent))


def test_player_defeat_opens_game_over_choice():
    bus = EventBus()
    world = create_world(bus)
    grant_player_abilities(world, ("tactical_shift",))
    DefeatSystem(world, bus)
    human = _human_entity(world)

    captured = {}
    bus.subscribe(EVENT_PLAYER_DEFEATED, lambda sender, **payload: captured.update(payload))

    bus.emit(EVENT_ENTITY_DEFEATED, entity=human)

    assert captured.get("entity") == human
    choices = list(world.get_component(GameOverChoice))
    assert len(choices) == 1
    choice_entity, choice_comp = choices[0]
    assert choice_comp.action == "return_to_menu"
    windows = list(world.get_component(ChoiceWindow))
    assert len(windows) == 1
    option_window = world.component_for_entity(choice_entity, ChoiceOption).window_entity
    assert option_window == windows[0][0]


def test_return_to_menu_resets_state_and_spawns_menu():
    bus = EventBus()
    world = create_world(bus)
    grant_player_abilities(world, ("tactical_shift",))
    defeat = DefeatSystem(world, bus)
    human = _human_entity(world)

    # Prime some mutable state that should be cleared.
    player_bank: TileBank = world.component_for_entity(human, TileBank)
    player_bank.counts["blood"] = 4
    human_health: Health = world.component_for_entity(human, Health)
    human_health.current = 7
    owner: AbilityListOwner = world.component_for_entity(human, AbilityListOwner)
    assert owner.ability_entities, "expected default ability entity for player"
    ability_entity = owner.ability_entities[0]
    world.add_component(ability_entity, AbilityCooldown(remaining_turns=3))

    state = next(comp for _, comp in world.get_component(GameState))
    state.mode = GameMode.COMBAT

    bus.emit(EVENT_ENTITY_DEFEATED, entity=human)

    choice_entity = next(ent for ent, _ in world.get_component(GameOverChoice))
    option = world.component_for_entity(choice_entity, ChoiceOption)
    window_entity = option.window_entity

    reset_payload = {}
    bus.subscribe(EVENT_COMBAT_RESET, lambda sender, **payload: reset_payload.update(payload))

    bus.emit(
        EVENT_CHOICE_SELECTED,
        window_entity=window_entity,
        choice_entity=choice_entity,
        payload_entity=None,
    )

    assert reset_payload.get("reason") == "player_defeated"
    assert state.mode == GameMode.MENU
    assert list(world.get_component(MenuButton)), "expected menu button after returning to menu"
    assert player_bank.counts == {}
    owner = world.component_for_entity(human, AbilityListOwner)
    assert owner.ability_entities == []
    human_health = world.component_for_entity(human, Health)
    assert human_health.current == human_health.max_hp
    assert not list(world.get_component(ChoiceWindow))
    with pytest.raises((KeyError, ValueError)):
        world.component_for_entity(ability_entity, AbilityCooldown)


def test_enemy_defeat_resets_combat_state():
    bus = EventBus()
    world = create_world(bus)
    grant_player_abilities(world, ("tactical_shift",))
    DefeatSystem(world, bus)
    human = _human_entity(world)
    enemy = _enemy_entity(world)

    human_bank: TileBank = world.component_for_entity(human, TileBank)
    enemy_bank: TileBank = world.component_for_entity(enemy, TileBank)
    human_bank.counts["blood"] = 2
    enemy_bank.counts["nature"] = 5

    owner: AbilityListOwner = world.component_for_entity(human, AbilityListOwner)
    ability_entity = owner.ability_entities[0]
    world.add_component(ability_entity, AbilityCooldown(remaining_turns=5))
    world.add_component(
        ability_entity,
        PendingAbilityTarget(
            ability_entity=ability_entity,
            owner_entity=human,
            row=0,
            col=0,
        ),
    )
    world.add_component(human, TargetingState(ability_entity=ability_entity))

    try:
        effect_list = world.component_for_entity(human, EffectList)
    except KeyError:
        effect_list = EffectList()
        world.add_component(human, effect_list)
    effect_entity = world.create_entity(Effect(slug="mark", owner_entity=human))
    effect_list.effect_entities.append(effect_entity)

    turn_order_entity = world.create_entity(TurnOrder(owners=[human, enemy], index=1))
    world.create_entity(ActiveTurn(owner_entity=enemy))

    enemy_health: Health = world.component_for_entity(enemy, Health)
    enemy_health.current = 0
    human_health: Health = world.component_for_entity(human, Health)
    human_health.current = max(1, human_health.current - 10)
    preserved_health = human_health.current

    reset_payload = {}
    bus.subscribe(EVENT_COMBAT_RESET, lambda sender, **payload: reset_payload.update(payload))

    bus.emit(EVENT_ENTITY_DEFEATED, entity=enemy)

    assert reset_payload.get("reason") == "enemy_defeated"
    assert reset_payload.get("defeated_entity") == enemy

    human_bank = world.component_for_entity(human, TileBank)
    new_enemy = _enemy_entity(world)
    enemy_bank = world.component_for_entity(new_enemy, TileBank)
    assert human_bank.counts == {}
    assert enemy_bank.counts == {}

    cooldown = world.component_for_entity(ability_entity, AbilityCooldown)
    assert cooldown.remaining_turns == 0
    assert not list(world.get_component(TargetingState))
    assert not list(world.get_component(PendingAbilityTarget))
    with pytest.raises((KeyError, ValueError)):
        world.component_for_entity(effect_entity, Effect)

    human_health = world.component_for_entity(human, Health)
    enemy_health = world.component_for_entity(new_enemy, Health)
    assert human_health.current == preserved_health
    assert enemy_health.current == enemy_health.max_hp

    turn_order = world.component_for_entity(turn_order_entity, TurnOrder)
    assert turn_order.index == 0
    assert turn_order.owners[0] == human
    assert turn_order.owners[1] == new_enemy
    active_turn = list(world.get_component(ActiveTurn))[0][1]
    assert active_turn.owner_entity == human

    assert not list(world.get_component(GameOverChoice))
    assert not find_all_matches(world)


def test_combat_reset_clears_tile_effects():
    bus = EventBus()
    world = create_world(bus)
    grant_player_abilities(world, ("tactical_shift",))
    DefeatSystem(world, bus)
    board = BoardSystem(world, bus, rows=2, cols=2)

    tile_entity = board._get_entity_at(0, 0)
    assert tile_entity is not None
    enemy = _enemy_entity(world)

    try:
        effect_list = world.component_for_entity(tile_entity, EffectList)
    except KeyError:
        effect_list = EffectList()
        world.add_component(tile_entity, effect_list)
    guard_effect = Effect(
        slug="tile_guarded",
        owner_entity=tile_entity,
        metadata={"source_owner": enemy},
    )
    effect_entity = world.create_entity(guard_effect)
    effect_list.effect_entities.append(effect_entity)

    bus.emit(EVENT_ENTITY_DEFEATED, entity=enemy)

    with pytest.raises((KeyError, ValueError)):
        world.component_for_entity(effect_entity, Effect)

    try:
        updated_list = world.component_for_entity(tile_entity, EffectList)
    except (KeyError, ValueError):
        updated_list = None
    assert updated_list is None or not updated_list.effect_entities
