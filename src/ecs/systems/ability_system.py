from esper import World

from ecs.events.bus import EventBus
from ecs.systems.ability_activation_system import AbilityActivationSystem
from ecs.systems.ability_resolution_system import AbilityResolutionSystem
from ecs.systems.ability_cooldown_system import AbilityCooldownSystem
from ecs.systems.ability_choice_system import AbilityChoiceSystem
from ecs.systems.abilities.base import AbilityResolver


class AbilitySystem:
    """Composition root for ability activation and resolution phases."""

    def __init__(
        self,
        world: World,
        event_bus: EventBus,
        resolvers: dict[str, AbilityResolver] | None = None,
    ) -> None:
        self.world = world
        self.event_bus = event_bus
        self.activation = AbilityActivationSystem(world, event_bus)
        self.resolution = AbilityResolutionSystem(world, event_bus, resolvers)
        self.cooldown = AbilityCooldownSystem(world, event_bus)
        self.choice = AbilityChoiceSystem(world, event_bus)

