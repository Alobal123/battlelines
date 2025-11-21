from __future__ import annotations

from esper import World

from ecs.components.combatants import Combatants
from ecs.components.game_state import GameState


def find_primary_opponent(world: World, owner_entity: int | None) -> int | None:
    """Return the opposing combatant for ``owner_entity`` if known."""

    if owner_entity is None:
        return None

    combatants = _combatants(world)
    if combatants is not None:
        if owner_entity == combatants.player_entity:
            return combatants.opponent_entity
        if owner_entity == combatants.opponent_entity:
            return combatants.player_entity

    opponent = _fallback_opponent(world, owner_entity)
    return opponent


def set_combat_opponent(world: World, opponent_entity: int) -> None:
    """Ensure combatant tracking references ``opponent_entity`` as the rival."""

    combatants = _combatants(world)
    if combatants is not None:
        combatants.opponent_entity = opponent_entity
        return
    player = _first_player(world)
    if player is None:
        return
    _attach_combatants(world, player, opponent_entity)


def ensure_combatants(world: World, player_entity: int, opponent_entity: int) -> None:
    """Install or refresh the combatant pair."""

    combatants = _combatants(world)
    if combatants is None:
        _attach_combatants(world, player_entity, opponent_entity)
        return
    combatants.player_entity = player_entity
    combatants.opponent_entity = opponent_entity


def _combatants(world: World) -> Combatants | None:
    for _, comp in world.get_component(Combatants):
        return comp
    return None


def _attach_combatants(world: World, player_entity: int, opponent_entity: int) -> None:
    target_entity = _state_entity(world)
    if target_entity is None:
        target_entity = world.create_entity()
    try:
        world.add_component(
            target_entity,
            Combatants(player_entity=player_entity, opponent_entity=opponent_entity),
        )
    except ValueError:
        try:
            existing = world.component_for_entity(target_entity, Combatants)
        except (KeyError, ValueError):
            return
        existing.player_entity = player_entity
        existing.opponent_entity = opponent_entity


def _state_entity(world: World) -> int | None:
    for entity, _ in world.get_component(GameState):
        return entity
    return None


def _first_player(world: World) -> int | None:
    from ecs.components.human_agent import HumanAgent

    for entity, _ in world.get_component(HumanAgent):
        return entity
    return None


def _fallback_opponent(world: World, owner_entity: int) -> int | None:
    from ecs.components.human_agent import HumanAgent
    from ecs.components.rule_based_agent import RuleBasedAgent
    from ecs.components.health import Health
    from ecs.components.ability_list_owner import AbilityListOwner

    def _has(entity: int, component_type) -> bool:
        try:
            world.component_for_entity(entity, component_type)
        except (KeyError, ValueError):
            return False
        return True

    candidates: list[int] = []

    if _has(owner_entity, HumanAgent):
        candidates.extend(ent for ent, _ in world.get_component(RuleBasedAgent) if ent != owner_entity)
    elif _has(owner_entity, RuleBasedAgent):
        candidates.extend(ent for ent, _ in world.get_component(HumanAgent) if ent != owner_entity)

    prioritized = [ent for ent in candidates if _has(ent, Health)]
    if prioritized:
        return prioritized[0]
    if candidates:
        return candidates[0]

    ability_owners: list[int] = [ent for ent, _ in world.get_component(AbilityListOwner) if ent != owner_entity]
    prioritized = [ent for ent in ability_owners if _has(ent, Health)]
    if prioritized:
        return prioritized[0]
    if ability_owners:
        return ability_owners[0]

    for ent, _ in world.get_component(Health):
        if ent != owner_entity:
            return ent

    return None
