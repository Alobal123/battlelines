import pytest
from esper import World
from ecs.events.bus import EventBus, EVENT_TILE_BANK_SPENT, EVENT_ABILITY_ACTIVATE_REQUEST, EVENT_TILE_CLICK
from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.human_agent import HumanAgent
from ecs.components.tile_bank import TileBank
from ecs.components.board_position import BoardPosition
from ecs.components.tile import TileType
from ecs.components.active_switch import ActiveSwitch
from ecs.components.tile_type_registry import TileTypeRegistry
from ecs.components.tile_types import TileTypes
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.ability_targeting_system import AbilityTargetingSystem
from ecs.systems.effect_lifecycle_system import EffectLifecycleSystem
from ecs.systems.effects.board_transform_effect_system import BoardTransformEffectSystem
from ecs.components.board import Board
from ecs.components.ability_effect import AbilityEffectSpec, AbilityEffects

class DummyBus(EventBus):
    pass

@pytest.fixture
def world_and_bus():
    bus = DummyBus()
    world = World()
    # Create canonical type definitions entity
    world.create_entity(
        TileTypeRegistry(),
        TileTypes(types={
            'infantry': (70,90,180),
            'ranged': (180,60,60),
            'cavalry': (80,170,80),
        })
    )
    world.create_entity(Board(rows=2, cols=2))
    target_color_name = 'cavalry'
    # Build minimal 2x2 board with one infantry to transform
    for r in range(2):
        for c in range(2):
            ent = world.create_entity(
                BoardPosition(row=r, col=c),
                TileType(type_name='infantry' if (r == 0 and c == 0) else 'ranged'),
                ActiveSwitch(active=True),
            )
    ability_entity = world.create_entity(
        Ability(
            name='tactical_shift',
            kind='active',
            cost={'infantry':1},
            params={'target_color': target_color_name},
        ),
        AbilityTarget(target_type='tile', max_targets=1),
        AbilityEffects(
            effects=(
                AbilityEffectSpec(
                    slug='board_transform_type',
                    target='board',
                    metadata={
                        'target_type': target_color_name,
                        'reason': 'tactical_shift',
                    },
                    param_overrides={'target_type': 'target_color'},
                ),
            ),
        ),
    )
    player_ent = world.create_entity(HumanAgent(), AbilityListOwner(ability_entities=[ability_entity]), TileBank(owner_entity=0))
    bank = world.component_for_entity(player_ent, TileBank)
    bank.owner_entity = player_ent
    bank.counts['infantry'] = 5
    AbilityTargetingSystem(world, bus)
    AbilitySystem(world, bus)
    EffectLifecycleSystem(world, bus)
    BoardTransformEffectSystem(world, bus)
    return world, bus, ability_entity, player_ent, target_color_name

def test_tactical_shift_configurable_color(world_and_bus):
    world, bus, ability_entity, player_ent, target_color_name = world_and_bus
    # Activate ability (enter targeting)
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=ability_entity, owner_entity=player_ent)
    # Select target tile which triggers spend request; then simulate spend success
    bus.emit(EVENT_TILE_CLICK, row=0, col=0)
    bus.emit(EVENT_TILE_BANK_SPENT, entity=player_ent, ability_entity=ability_entity, cost={'infantry':1})
    # Assert tile at (0,0) now has target color type_name
    for ent, pos in world.get_component(BoardPosition):
        if pos.row == 0 and pos.col == 0:
            tile = world.component_for_entity(ent, TileType)
            assert tile.type_name == target_color_name
            break
