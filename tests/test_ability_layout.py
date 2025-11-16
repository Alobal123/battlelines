from ecs.ui.ability_layout import compute_ability_layout
from ecs.components.ability import Ability

class DummyAbility(Ability):
    pass

def test_compute_ability_layout_stacking_and_affordability():
    abilities = [
        (1, Ability(name="a1", kind="active", cost={"red":2})),
        (2, Ability(name="a2", kind="active", cost={"blue":3,"red":1})),
        (3, Ability(name="a3", kind="active", cost={}))
    ]
    bank = {"red":2, "blue":1}
    layout = compute_ability_layout(abilities, bank, owner_entity=999, start_x=10, start_top=200, rect_w=100, rect_h=40, spacing=5)
    assert len(layout) == 3
    # Stacking y positions strictly descending
    assert layout[0]['y'] == 200
    assert layout[1]['y'] == 200 - (40 + 5)
    assert layout[2]['y'] == 200 - 2*(40 + 5)
    # Affordability flags
    assert layout[0]['affordable'] is True  # red 2 available
    assert layout[1]['affordable'] is False # blue insufficient
    assert layout[2]['affordable'] is True  # empty cost always affordable
    # Geometry fields present
    for entry in layout:
        for key in ('entity','slug','name','cost','affordable','x','y','width','height','index'):
            assert key in entry
    # Labels formatted while slugs preserved
    assert layout[0]['slug'] == 'a1'
    assert layout[0]['name'] == 'A1'
