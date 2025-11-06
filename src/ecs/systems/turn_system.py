from esper import World
from ecs.events.bus import EventBus, EVENT_MATCH_CLEARED, EVENT_CASCADE_COMPLETE, EVENT_ABILITY_EFFECT_APPLIED, EVENT_TURN_ADVANCED
from ecs.components.turn_order import TurnOrder
from ecs.components.active_turn import ActiveTurn
from ecs.components.ability_list_owner import AbilityListOwner

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
        self.event_bus.subscribe(EVENT_MATCH_CLEARED, self.on_match_cleared)
        self.event_bus.subscribe(EVENT_CASCADE_COMPLETE, self.on_cascade_complete)
        self.event_bus.subscribe(EVENT_ABILITY_EFFECT_APPLIED, self.on_ability_effect_applied)
        self.rotation_pending = False
        self._ensure_turn_order()

    def _ensure_turn_order(self):
        # If no TurnOrder component, create one using current owners
        existing = list(self.world.get_component(TurnOrder))
        if existing:
            return
        owners = [ent for ent, comp in self.world.get_component(AbilityListOwner)]
        ent = self.world.create_entity(TurnOrder(owners=owners, index=0))
        # Initialize ActiveTurn if missing
        if not list(self.world.get_component(ActiveTurn)) and owners:
            self.world.create_entity(ActiveTurn(owner_entity=owners[0]))

    def on_match_cleared(self, sender, **payload):
        # Set rotation pending (only first time in a cascade). Multiple match_cleared within cascade should not queue multiple advances.
        if not self.rotation_pending:
            self.rotation_pending = True

    def on_ability_effect_applied(self, sender, **payload):
        # Ensure abilities always advance turn after cascade completion (even if no matches occur).
        if not self.rotation_pending:
            self.rotation_pending = True

    def on_cascade_complete(self, sender, **payload):
        if not self.rotation_pending:
            return
        self.rotation_pending = False
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
