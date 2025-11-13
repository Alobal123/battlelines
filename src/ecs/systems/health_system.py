from esper import World

from ecs.components.health import Health
from ecs.events.bus import EventBus, EVENT_HEALTH_DAMAGE, EVENT_HEALTH_CHANGED


class HealthSystem:
    """Manages health state changes via events.
    
    Subscribes to EVENT_HEALTH_DAMAGE and applies damage to target entities.
    Emits EVENT_HEALTH_CHANGED after mutations to allow other systems to react.
    """
    
    def __init__(self, world: World, event_bus: EventBus):
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_HEALTH_DAMAGE, self.on_health_damage)
    
    def on_health_damage(self, sender, **kwargs):
        """Apply damage to target entity and emit health changed event."""
        target_entity = kwargs.get('target_entity')
        amount = kwargs.get('amount', 0)
        source_owner = kwargs.get('source_owner')
        reason = kwargs.get('reason', 'unknown')
        
        if target_entity is None or amount <= 0:
            return
        
        try:
            health = self.world.component_for_entity(target_entity, Health)
        except KeyError:
            return
        
        old_hp = health.current
        health.current -= amount
        health.clamp()
        delta = health.current - old_hp
        
        self.event_bus.emit(
            EVENT_HEALTH_CHANGED,
            entity=target_entity,
            current=health.current,
            max_hp=health.max_hp,
            delta=delta,
            reason=reason,
            source_owner=source_owner,
        )
