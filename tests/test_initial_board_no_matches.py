from ecs.events.bus import EventBus
from ecs.world import create_world
from ecs.systems.board import BoardSystem
from ecs.components.tile import TileColor
from ecs.components.board_position import BoardPosition

def has_match(world, rows, cols):
    # scan horizontal & vertical
    # build map
    colors = {}
    for ent, pos in world.get_component(BoardPosition):
        color_comp = world.component_for_entity(ent, TileColor)
        colors[(pos.row, pos.col)] = color_comp.color
    # horizontal
    for r in range(rows):
        run=[]; last=None
        for c in range(cols):
            colr=colors[(r,c)]
            if colr==last:
                run.append((r,c))
            else:
                if len(run)>=3:
                    return True
                run=[(r,c)]
                last=colr
        if len(run)>=3:
            return True
    for c in range(cols):
        run=[]; last=None
        for r in range(rows):
            colr=colors[(r,c)]
            if colr==last:
                run.append((r,c))
            else:
                if len(run)>=3:
                    return True
                run=[(r,c)]
                last=colr
        if len(run)>=3:
            return True
    return False

def test_initial_board_has_no_matches():
    bus=EventBus(); world=create_world(bus); board=BoardSystem(world,bus,8,8)
    assert not has_match(world,8,8), 'Initial board should not contain any matches'
