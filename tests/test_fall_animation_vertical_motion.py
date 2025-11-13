from ecs.events.bus import EventBus, EVENT_TILE_SWAP_REQUEST, EVENT_TICK
from ecs.world import create_world
from ecs.systems.board import BoardSystem
from ecs.systems.animation import AnimationSystem
from ecs.systems.match import MatchSystem
from ecs.systems.match_resolution import MatchResolutionSystem
from ecs.systems.turn_system import TurnSystem
from ecs.systems.render import RenderSystem
from ecs.components.tile import TileType
from ecs.components.active_switch import ActiveSwitch

class DummyWindow:
    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height

def drive_ticks(bus, count=1, dt=0.02):
    for _ in range(count):
        bus.emit(EVENT_TICK, dt=dt)

def test_vertical_motion_interpolates_from_source_row():
    bus = EventBus(); world = create_world(bus); window = DummyWindow()
    board = BoardSystem(world, bus, 5, 5)
    MatchSystem(world, bus); AnimationSystem(world, bus); TurnSystem(world, bus); mr = MatchResolutionSystem(world, bus)
    render = RenderSystem(world, bus, window)
    # Pattern to create vertical match after swap (3,0)<->(4,0)
    e = [board._get_entity_at(r,0) for r in range(5)]
    names = ['hex','hex','hex','nature','hex']
    for ent,name in zip(e,names):
        assert ent is not None
        world.component_for_entity(ent, TileType).type_name = name
        world.component_for_entity(ent, ActiveSwitch).active = True
    bus.emit(EVENT_TILE_SWAP_REQUEST, src=(3,0), dst=(4,0))
    # Drive ticks until fall animation components appear (swap + fade + gravity)
    from ecs.components.animation_fall import FallAnimation
    fall_list = []
    for _ in range(120):  # up to ~2.4s simulated time
        drive_ticks(bus, 1)
        fall_list = list(world.get_component(FallAnimation))
        if fall_list:
            break
    assert fall_list, 'Fall animation components not created within expected ticks'
    render.process()
    _, first_fall = fall_list[0]
    src = first_fall.src; target = first_fall.dst
    # At early progress fall.linear should be <1; capture draw coords
    # Process another frame to populate/interpolate
    drive_ticks(bus, 1)
    render.process()
    draw = getattr(render, '_last_draw_coords', {})
    assert target in draw, f'Target cell {target} not drawn'
    src_center_y = None
    target_center_y = None
    # Compute expected centers
    tile_size = render._tile_size
    from ecs.constants import BOTTOM_MARGIN
    start_y = BOTTOM_MARGIN
    src_center_y = start_y + src[0]*tile_size + tile_size/2
    target_center_y = start_y + target[0]*tile_size + tile_size/2
    actual_y = draw[target][1]
    assert actual_y != target_center_y, 'Vertical motion not interpolating (already at destination)'
    # Should be between src and target y
    low = min(src_center_y, target_center_y) - 1
    high = max(src_center_y, target_center_y) + 1
    assert low <= actual_y <= high, 'Interpolated Y outside expected range'
