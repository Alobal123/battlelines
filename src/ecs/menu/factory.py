"""Factory helpers for creating the main menu entities."""
from esper import World

from ecs.components.story_progress_tracker import StoryProgressTracker
from ecs.menu.components import MenuAction, MenuBackground, MenuButton, MenuTag


def spawn_main_menu(
    world: World,
    width: int,
    height: int,
    *,
    enable_continue: bool | None = None,
) -> None:
    """Create the menu background and buttons for starting or continuing the game."""
    center_x = width / 2
    center_y = height / 2

    background_entity = world.create_entity()
    world.add_component(background_entity, MenuBackground())
    world.add_component(background_entity, MenuTag())

    if enable_continue is None:
        enable_continue = any(
            tracker.enemies_defeated > 0
            for _, tracker in world.get_component(StoryProgressTracker)
        )

    continue_y = center_y + 80.0 if enable_continue else center_y + 60.0
    new_game_y = center_y - 20.0 if enable_continue else center_y
    button_specs = (
        ("Continue", MenuAction.CONTINUE, continue_y, enable_continue),
        ("New Game", MenuAction.NEW_GAME, new_game_y, True),
    )

    for label, action, y_position, enabled in button_specs:
        button_entity = world.create_entity()
        world.add_component(
            button_entity,
            MenuButton(
                label=label,
                action=action,
                x=center_x,
                y=y_position,
                enabled=bool(enabled),
            ),
        )
        world.add_component(button_entity, MenuTag())
