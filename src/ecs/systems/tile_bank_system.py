from esper import World
from typing import Dict
from ecs.events.bus import (
    EventBus,
    EVENT_MATCH_CLEARED,
    EVENT_TILE_BANK_CHANGED,
    EVENT_TILE_BANK_SPEND_REQUEST,
    EVENT_TILE_BANK_SPENT,
    EVENT_TILE_BANK_INSUFFICIENT,
)
from ecs.components.tile_bank import TileBank
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.systems.board import COLOR_NAME_MAP

class TileBankSystem:
    """Tracks cleared tiles and manages spending for abilities.

    Logic:
      - On EVENT_MATCH_CLEARED: increment counts for the owner's bank (assumes single player for now).
      - On EVENT_TILE_BANK_SPEND_REQUEST: validate and spend or emit insufficient.
        Assumptions:
            - Single player entity with AbilityListOwner; extend later for multiple players.
      - colors payload from match cleared includes (r,c,color_tuple); we map color_name from tuple via ability cost keys.
        For now we treat raw RGB tuples as not directly useful: spending expects semantic type names, so ensure future
        pipeline translates match colors to type names if required.
    """
    def __init__(self, world: World, event_bus: EventBus):
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_MATCH_CLEARED, self.on_match_cleared)
        self.event_bus.subscribe(EVENT_TILE_BANK_SPEND_REQUEST, self.on_spend_request)

    def _get_or_create_bank(self, owner_entity: int) -> int:
        # Find existing bank for owner or create one.
        for ent, bank in self.world.get_component(TileBank):
            if bank.owner_entity == owner_entity:
                return ent
        bank_ent = self.world.create_entity(TileBank(owner_entity=owner_entity))
        return bank_ent

    from typing import Optional
    def _list_owners(self) -> list:
        return [ent for ent, comp in self.world.get_component(AbilityListOwner)]

    def on_match_cleared(self, sender, **kwargs):
        positions = kwargs.get('positions', [])
        colors = kwargs.get('colors', [])  # list of (r,c,color_tuple)
        owner_entity = kwargs.get('owner_entity')
        if owner_entity is None:
            owners = self._list_owners()
            if not owners:
                return
            owner_entity = owners[0]
        bank_ent = self._get_or_create_bank(owner_entity)
        bank: TileBank = self.world.component_for_entity(bank_ent, TileBank)
        # Currently we don't have direct type_name in payload; approximate from RGB stringified
        for (_, _, color) in colors:
            if color is None:
                continue
            type_key = COLOR_NAME_MAP.get(color)
            if not type_key:
                # Fallback to rgb string if color not recognized
                r,g,b = color
                type_key = f"{r}_{g}_{b}"
            bank.add(type_key, 1)
        self.event_bus.emit(EVENT_TILE_BANK_CHANGED, entity=bank_ent, counts=bank.counts.copy())

    def on_spend_request(self, sender, **kwargs):
        owner_entity = kwargs.get('entity')
        cost: Dict[str, int] = kwargs.get('cost', {})
        ability_entity = kwargs.get('ability_entity')
        if owner_entity is None or not cost:
            return
        # Find bank for owner
        bank_ent = None
        for ent, bank in self.world.get_component(TileBank):
            if bank.owner_entity == owner_entity:
                bank_ent = ent
                bank_obj = bank
                break
        if bank_ent is None:
            # No bank yet; create then fail
            bank_ent = self._get_or_create_bank(owner_entity)
            bank_obj: TileBank = self.world.component_for_entity(bank_ent, TileBank)
        else:
            bank_obj = bank_obj  # already set in loop
        missing = bank_obj.spend(cost)
        if missing:
            self.event_bus.emit(EVENT_TILE_BANK_INSUFFICIENT, entity=bank_ent, cost=cost, missing=missing, ability_entity=ability_entity)
        else:
            self.event_bus.emit(EVENT_TILE_BANK_SPENT, entity=bank_ent, cost=cost, ability_entity=ability_entity)
            self.event_bus.emit(EVENT_TILE_BANK_CHANGED, entity=bank_ent, counts=bank_obj.counts.copy())

    def process(self):
        # Not used per-frame currently
        return
