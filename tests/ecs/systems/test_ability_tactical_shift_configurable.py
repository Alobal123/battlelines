import pytest
from esper import World
from ecs.events.bus import EventBus, EVENT_TILE_BANK_SPEND_REQUEST, EVENT_TILE_BANK_SPENT, EVENT_ABILITY_ACTIVATE_REQUEST, EVENT_ABILITY_TARGET_MODE, EVENT_TILE_CLICK
from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.human_agent import HumanAgent
from ecs.components.tile_bank import TileBank
from ecs.components.board_position import BoardPosition
from ecs.components.tile import TileType
from ecs.systems.ability_system import AbilitySystem
from ecs.systems.board import NAME_TO_COLOR

class DummyBus(EventBus):
    pass

@pytest.fixture
def world_and_bus():
    bus = DummyBus()
    world = World()
    # Build minimal board with two colors
    colors = list(NAME_TO_COLOR.values())
    # Ensure at least one tile of a source color (blue) to convert
    source_color = NAME_TO_COLOR.get('blue')
    target_color_name = 'green'
    # Create some entities
    for r in range(2):
        for c in range(2):
            color = source_color if (r == 0 and c == 0) else NAME_TO_COLOR.get('red')
            world.create_entity(BoardPosition(row=r, col=c), TileType(type_name='blue' if color == source_color else 'red', color_name=None, raw_color=color))
    ability_entity = world.create_entity(Ability(name='tactical_shift', kind='active', cost={'blue':1}, params={'target_color': target_color_name}), AbilityTarget(target_type='tile', max_targets=1))
    player_ent = world.create_entity(HumanAgent(), AbilityListOwner(ability_entities=[ability_entity]), TileBank(owner_entity=0))
    bank = world.component_for_entity(player_ent, TileBank)
    bank.owner_entity = player_ent
    bank.counts['blue'] = 5
    AbilitySystem(world, bus)
    return world, bus, ability_entity, player_ent, target_color_name

def test_tactical_shift_configurable_color(world_and_bus):
    world, bus, ability_entity, player_ent, target_color_name = world_and_bus
    # Simulate activation (spend should succeed immediately since bank populated)
    bus.emit(EVENT_ABILITY_ACTIVATE_REQUEST, ability_entity=ability_entity, owner_entity=player_ent)
    # Directly emit bank spent (bypassing TileBankSystem for unit isolation)
    bus.emit(EVENT_TILE_BANK_SPENT, entity=player_ent, ability_entity=ability_entity, cost={'blue':1})
    # Click on the source tile (0,0)
    bus.emit(EVENT_TILE_CLICK, row=0, col=0)
    # Assert tile at (0,0) now has target color type_name
    for ent, pos in world.get_component(BoardPosition):
        if pos.row == 0 and pos.col == 0:
            tile = world.component_for_entity(ent, TileType)
            assert tile.type_name == target_color_name
            assert tile.color_name == target_color_name
            assert tile.raw_color == NAME_TO_COLOR.get(target_color_name)
            break
