"""Factory helpers for creating the main menu entities."""
from esper import World
from ecs.menu.components import MenuBackground, MenuButton, MenuAction, MenuTag


def spawn_main_menu(world: World, width: int, height: int) -> None:
    """Create the menu background and the single "New Game" button."""
    center_x = width / 2
    center_y = height / 2

    background_entity = world.create_entity()
    world.add_component(background_entity, MenuBackground())
    world.add_component(background_entity, MenuTag())

    button_entity = world.create_entity()
    world.add_component(
        button_entity,
        MenuButton(
            label="New Game",
            action=MenuAction.NEW_GAME,
            x=center_x,
            y=center_y,
        ),
    )
    world.add_component(button_entity, MenuTag())
