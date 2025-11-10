from ecs.world import create_world
from ecs.events.bus import EventBus
from ecs.components.regiments_query import get_regiments_for_owner
from ecs.components.human_agent import HumanAgent

def test_each_player_has_three_regiments():
    bus = EventBus()
    world = create_world(bus)
    players = [ent for ent, _ in world.get_component(HumanAgent)]
    assert len(players) >= 2
    for p in players[:2]:
        regs = get_regiments_for_owner(world, p)
        assert len(regs) == 3, f"Owner {p} expected 3 regiments, got {len(regs)}"
        types = [r.unit_type for _, r in regs]
    assert set(types) == {"infantry", "cavalry", "ranged"}
