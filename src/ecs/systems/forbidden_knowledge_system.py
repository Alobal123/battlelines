from esper import World

from ecs.components.forbidden_knowledge import ForbiddenKnowledge
from ecs.events.bus import (
    EventBus,
    EVENT_TILES_MATCHED,
    EVENT_FORBIDDEN_KNOWLEDGE_CHANGED,
    EVENT_TILE_BANK_CHANGED,
)
from ecs.components.tile import TileType
from ecs.components.tile_bank import TileBank
from ecs.systems.board_ops import get_tile_registry


class ForbiddenKnowledgeSystem:
    """Accumulates Forbidden Knowledge when Secrets tiles are cleared."""

    def __init__(self, world: World, event_bus: EventBus):
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_TILES_MATCHED, self.on_tiles_matched)
        self.event_bus.subscribe(EVENT_TILE_BANK_CHANGED, self.on_bank_changed)

    def on_tiles_matched(self, sender, **kwargs) -> None:
        types = kwargs.get("types") or []
        secrets_cleared = sum(1 for _, _, tile_type in types if tile_type == "secrets")
        if secrets_cleared <= 0:
            return
        self._increment_meter(secrets_cleared)

    def on_bank_changed(self, sender, **kwargs) -> None:
        if kwargs.get("source") != "knowledge_bar_click":
            return
        delta = kwargs.get("delta") or {}
        amount = delta.get("secrets")
        try:
            amount_int = int(amount)
        except (TypeError, ValueError):
            amount_int = 0
        if amount_int <= 0:
            return
        self._increment_meter(amount_int)

    def process(self):
        # No per-frame processing needed; event driven.
        return

    def _increment_meter(self, amount: int) -> None:
        if amount <= 0:
            return
        for entity, meter in self.world.get_component(ForbiddenKnowledge):
            previous = meter.value
            meter.value = min(meter.max_value, previous + amount)
            delta = meter.value - previous
            if delta:
                self.event_bus.emit(
                    EVENT_FORBIDDEN_KNOWLEDGE_CHANGED,
                    entity=entity,
                    value=meter.value,
                    max_value=meter.max_value,
                    delta=delta,
                )
            if meter.value >= meter.max_value and not meter.chaos_released:
                self._release_chaos(meter)

    def _release_chaos(self, meter: ForbiddenKnowledge) -> None:
        registry = None
        try:
            registry = get_tile_registry(self.world)
        except RuntimeError:
            registry = None
        meter.chaos_released = True
        if registry is not None:
            if "chaos" not in registry.defined_types():
                registry.register_type("chaos", (241, 198, 184), spawnable=False)
            current_spawnable = registry.spawnable_types()
            updated = [name for name in current_spawnable if name != "secrets"]
            if "chaos" not in updated:
                updated.append("chaos")
            registry.set_spawnable(updated, allow_empty=False)
        for _, tile in self.world.get_component(TileType):
            if tile.type_name == "secrets":
                tile.type_name = "chaos"
        changed_banks: list[tuple[int, int, dict[str, int], dict[str, int]]] = []
        for bank_ent, bank in self.world.get_component(TileBank):
            secrets_stock = bank.counts.pop("secrets", 0)
            if secrets_stock:
                bank.counts["chaos"] = bank.counts.get("chaos", 0) + secrets_stock
                delta = {
                    "secrets": -secrets_stock,
                    "chaos": secrets_stock,
                }
                changed_banks.append((bank_ent, bank.owner_entity, bank.counts.copy(), delta))
        for bank_ent, owner_entity, counts, delta in changed_banks:
            self.event_bus.emit(
                EVENT_TILE_BANK_CHANGED,
                entity=bank_ent,
                owner_entity=owner_entity,
                counts=counts,
                delta=delta,
                source="forbidden_knowledge_chaos_release",
            )
