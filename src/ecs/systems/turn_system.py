from esper import World
from ecs.events.bus import (
    EventBus,
    EVENT_ABILITY_EFFECT_APPLIED,
    EVENT_CASCADE_COMPLETE,
    EVENT_CASCADE_STEP,
    EVENT_MATCH_CLEARED,
    EVENT_TURN_ACTION_STARTED,
    EVENT_TURN_ADVANCED,
    EVENT_EXTRA_TURN_GRANTED,
)
from ecs.components.turn_order import TurnOrder
from ecs.components.active_turn import ActiveTurn
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.turn_state import TurnState
from ecs.components.human_agent import HumanAgent
from ecs.components.ability import Ability
from ecs.systems.turn_state_utils import get_or_create_turn_state

class TurnSystem:
    """Rotates active owner only after cascades finish.

    Flow:
      - On first EVENT_MATCH_CLEARED within a cascade chain, set a pending rotation flag.
      - When EVENT_CASCADE_COMPLETE fires, if rotation pending, advance turn and clear flag.
    This preserves active owner through all cascading clears from a single move.
    """
    def __init__(self, world: World, event_bus: EventBus):
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_TURN_ACTION_STARTED, self.on_turn_action_started)
        self.event_bus.subscribe(EVENT_MATCH_CLEARED, self.on_match_cleared)
        self.event_bus.subscribe(EVENT_CASCADE_STEP, self.on_cascade_step)
        self.event_bus.subscribe(EVENT_CASCADE_COMPLETE, self.on_cascade_complete)
        self.event_bus.subscribe(EVENT_ABILITY_EFFECT_APPLIED, self.on_ability_effect_applied)
        self.rotation_pending = False
        self._ensure_turn_order()
        self._ensure_turn_state()

    def _ensure_turn_order(self):
        # If no TurnOrder component, create one using current owners
        existing = list(self.world.get_component(TurnOrder))
        if existing:
            return
        owners = [ent for ent, comp in self.world.get_component(AbilityListOwner)]
        if owners:
            human_entities = {ent for ent, _ in self.world.get_component(HumanAgent)}
            owners.sort(key=lambda entity: (entity not in human_entities, entity))
        ent = self.world.create_entity(TurnOrder(owners=owners, index=0))
        # Initialize ActiveTurn if missing
        if not list(self.world.get_component(ActiveTurn)) and owners:
            self.world.create_entity(ActiveTurn(owner_entity=owners[0]))

    def _ensure_turn_state(self):
        get_or_create_turn_state(self.world)

    def _turn_state(self) -> TurnState:
        return get_or_create_turn_state(self.world)

    def on_match_cleared(self, sender, **payload):
        # Set rotation pending (only first time in a cascade). Multiple match_cleared within cascade should not queue multiple advances.
        state = self._turn_state()
        if state.action_source == "ability" and not state.ability_ends_turn:
            return
        if not self.rotation_pending:
            self.rotation_pending = True

    def on_ability_effect_applied(self, sender, **payload):
        # Ensure abilities always advance turn after cascade completion (even if no matches occur).
        state = self._turn_state()
        ability_entity = payload.get("ability_entity")
        if (
            state.action_source == "ability"
            and not state.ability_ends_turn
            and (ability_entity is None or ability_entity == state.ability_entity)
        ):
            return
        if ability_entity is not None:
            try:
                ability = self.world.component_for_entity(ability_entity, Ability)
            except KeyError:
                ability = None
            if ability is not None and not ability.ends_turn:
                return
        if not self.rotation_pending:
            self.rotation_pending = True

    def on_turn_action_started(self, sender, **payload):
        state = self._turn_state()
        state.action_source = payload.get("source")
        state.cascade_active = False
        state.cascade_depth = 0
        state.cascade_observed = False
        ability_entity = payload.get("ability_entity")
        state.ability_entity = ability_entity
        state.ability_ends_turn = True
        if ability_entity is not None:
            try:
                ability = self.world.component_for_entity(ability_entity, Ability)
            except KeyError:
                ability = None
            if ability is not None:
                state.ability_ends_turn = ability.ends_turn

    def on_cascade_step(self, sender, **payload):
        state = self._turn_state()
        state.cascade_active = True
        state.cascade_observed = True
        state.cascade_depth = payload.get("depth", state.cascade_depth + 1)

    def on_cascade_complete(self, sender, **payload):
        state = self._turn_state()
        state.cascade_active = False
        state.cascade_depth = payload.get("depth", state.cascade_depth)
        state.cascade_observed = False
        state.action_source = None
        state.ability_entity = None
        state.ability_ends_turn = True
        owner_entity = self._current_owner()
        extra_turn = state.extra_turn_pending
        state.extra_turn_pending = False
        should_rotate = self.rotation_pending
        self.rotation_pending = False
        if extra_turn:
            if owner_entity is not None:
                self.event_bus.emit(
                    EVENT_EXTRA_TURN_GRANTED,
                    owner_entity=owner_entity,
                )
            return
        if not should_rotate:
            return
        self._advance_turn()
        
    def _advance_turn(self):
        """Advance turn order and update ActiveTurn component."""
        orders = list(self.world.get_component(TurnOrder))
        if not orders:
            return
        order_ent, order = orders[0]
        order.advance()
        new_owner = order.current()
        if new_owner is None:
            return
        active_list = list(self.world.get_component(ActiveTurn))
        previous_owner = None
        if not active_list:
            self.world.create_entity(ActiveTurn(owner_entity=new_owner))
        else:
            ent_active, comp_active = active_list[0]
            previous_owner = comp_active.owner_entity
            comp_active.owner_entity = new_owner
        self.event_bus.emit(EVENT_TURN_ADVANCED, previous_owner=previous_owner, new_owner=new_owner)

    def _current_owner(self) -> int | None:
        active_list = list(self.world.get_component(ActiveTurn))
        if not active_list:
            return None
        return active_list[0][1].owner_entity
