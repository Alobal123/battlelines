from esper import World
from .events.bus import EventBus
from ecs.components.human_agent import HumanAgent
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.ability import Ability
from ecs.components.ability_target import AbilityTarget
from ecs.components.tile_bank import TileBank
from ecs.components.tile_type_registry import TileTypeRegistry
from ecs.components.tile_types import TileTypes
from ecs.components.regiment import Regiment
from ecs.components.army_roster import ArmyRoster
from ecs.effects.registry import EffectDefinition, default_effect_registry, register_effect

def create_world(event_bus: EventBus) -> World:
    world = World()
    if not default_effect_registry.has("morale_boost"):
        register_effect(
            EffectDefinition(
                slug="morale_boost",
                display_name="Bolster Morale",
                description="Temporarily increases a regiment's morale.",
                tags=("morale", "buff"),
                default_metadata={"morale_bonus": 20, "turns": 3},
            )
        )
    # Shared ability definitions (each owner gets its own instances for independent pending targeting/components)
    def make_abilities():
        ability_shift = world.create_entity(
            Ability(name="tactical_shift", kind="active", cost={"ranged": 3, "infantry": 2}, params={"target_color": "ranged"}),
            AbilityTarget(target_type="tile", max_targets=1),
        )
        ability_pulse = world.create_entity(
            Ability(name="crimson_pulse", kind="active", cost={"ranged": 5}),
            AbilityTarget(target_type="tile", max_targets=1),
        )
        ability_morale = world.create_entity(
            Ability(
                name="bolster_morale",
                kind="active",
                cost={"tactics": 3},
                params={"morale_bonus": 20, "turns": 3},
            ),
            AbilityTarget(target_type="regiment", max_targets=1),
        )
        return [ability_shift, ability_pulse, ability_morale]

    # Player 1 (human)
    abilities_p1 = make_abilities()
    player1_ent = world.create_entity(
        HumanAgent(),
        AbilityListOwner(ability_entities=abilities_p1),
        TileBank(owner_entity=0)
    )
    bank1 = world.component_for_entity(player1_ent, TileBank)
    bank1.owner_entity = player1_ent
    # Player 2 (adversary placeholder; reuse HumanAgent for now until AI component added)
    abilities_p2 = make_abilities()
    player2_ent = world.create_entity(
        HumanAgent(),
        AbilityListOwner(ability_entities=abilities_p2),
        TileBank(owner_entity=0)
    )
    bank2 = world.component_for_entity(player2_ent, TileBank)
    bank2.owner_entity = player2_ent

    # Initial armies: each player gets three regiment entities (infantry, ranged, cavalry)
    def create_regiments(owner_ent: int, label: str, unit_order: list[str]):
        base_stats = {
            "num_men": 400,
            "combat_skill": 1.0,
            "armor_rating": 0.25,
            "manoeuvre": 0.7,
        }
        entities: list[int] = []
        for unit_type in unit_order:
            name = f"{unit_type.title()} {label}"
            entities.append(
                world.create_entity(
                    Regiment(
                        owner_id=owner_ent,
                        name=name,
                        unit_type=unit_type,
                        num_men=base_stats["num_men"],
                        combat_skill=base_stats["combat_skill"],
                        armor_rating=base_stats["armor_rating"],
                        manoeuvre=base_stats["manoeuvre"],
                    )
                )
            )
        return entities

    order_p1 = ["infantry", "ranged", "cavalry"]
    order_p2 = ["infantry", "ranged", "cavalry"]
    regiments_p1 = create_regiments(player1_ent, "P1", order_p1)
    regiments_p2 = create_regiments(player2_ent, "P2", order_p2)
    active_index_p1 = order_p1.index("infantry")
    active_index_p2 = order_p2.index("infantry")

    world.add_component(player1_ent, ArmyRoster(regiment_entities=regiments_p1, active_index=active_index_p1))
    world.add_component(player2_ent, ArmyRoster(regiment_entities=regiments_p2, active_index=active_index_p2))

    # Create single registry entity with canonical types
    registry_entity = world.create_entity(
        TileTypeRegistry(),
        TileTypes(types={
            'ranged': (180, 60, 60),
            'cavalry': (80, 170, 80),
            'infantry': (70, 90, 180),
            'logistics': (200, 190, 80),
            'plunder': (170, 80, 160),
            'subterfuge': (70, 170, 170),
            'tactics': (200, 130, 60),
        })
    )
    # TESTING: Prefill both banks generously with all type names
    definitions: TileTypes = world.component_for_entity(registry_entity, TileTypes)
    for type_name in definitions.types.keys():
        bank1.counts[type_name] = 100
        bank2.counts[type_name] = 100
    return world
