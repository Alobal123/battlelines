from ecs.events.bus import EventBus
from world import create_world
from ecs.systems.board import BoardSystem
from ecs.components.tile import TileType
from ecs.components.board_position import BoardPosition
from ecs.components.active_switch import ActiveSwitch

def has_match(world, rows, cols):
    # scan horizontal & vertical
    # build map
    types = {}
    for ent, pos in world.get_component(BoardPosition):
        try:
            active_sw: ActiveSwitch = world.component_for_entity(ent, ActiveSwitch)
        except KeyError:
            continue
        if not active_sw.active:
            continue
        tt = world.component_for_entity(ent, TileType)
        types[(pos.row, pos.col)] = tt.type_name
    # horizontal
    for r in range(rows):
        run=[]; last=None
        for c in range(cols):
            tval=types.get((r,c))
            if tval==last:
                run.append((r,c))
            else:
                if len(run)>=3:
                    return True
                run=[(r,c)]
                last=tval
        if len(run)>=3:
            return True
    for c in range(cols):
        run=[]; last=None
        for r in range(rows):
            tval=types.get((r,c))
            if tval==last:
                run.append((r,c))
            else:
                if len(run)>=3:
                    return True
                run=[(r,c)]
                last=tval
        if len(run)>=3:
            return True
    return False

def test_initial_board_has_no_matches():
    bus=EventBus(); world=create_world(bus); board=BoardSystem(world,bus,8,8)
    assert not has_match(world,8,8), 'Initial board should not contain any matches'
