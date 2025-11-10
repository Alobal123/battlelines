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
from ecs.components.tile_type_registry import TileTypeRegistry
from ecs.components.tile_types import TileTypes
from ecs.components.army_roster import ArmyRoster
from ecs.components.regiment import Regiment

class TileBankSystem:
    """Tracks cleared tiles and manages spending for abilities.

    Logic:
      - On EVENT_MATCH_CLEARED: increment counts for the owner's bank (assumes single player for now).
      - On EVENT_TILE_BANK_SPEND_REQUEST: validate and spend or emit insufficient.
        Assumptions:
            - Single player entity with AbilityListOwner; extend later for multiple players.
        Color is no longer processed here; semantic type names are the sole currency.
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
        positions = kwargs.get('positions', [])  # retained for possible future metrics
        types = kwargs.get('types', [])    # list of (r,c,type_name)
        owner_entity = kwargs.get('owner_entity')
        if owner_entity is None:
            owners = self._list_owners()
            if not owners:
                return
            owner_entity = owners[0]
        bank_ent = self._get_or_create_bank(owner_entity)
        bank: TileBank = self.world.component_for_entity(bank_ent, TileBank)
        readiness_gains: Dict[str, int] = {}
        for (_, _, type_name) in types:
            bank.add(type_name, 1)
            readiness_gains[type_name] = readiness_gains.get(type_name, 0) + 1
        if readiness_gains:
            self._apply_readiness_from_tiles(owner_entity, readiness_gains)
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

    def _registry(self) -> TileTypes:
        for ent, _ in self.world.get_component(TileTypeRegistry):
            return self.world.component_for_entity(ent, TileTypes)
        raise RuntimeError('TileTypes definitions not found')

    def _apply_readiness_from_tiles(self, owner_entity: int, gains: Dict[str, int]) -> None:
        try:
            roster: ArmyRoster = self.world.component_for_entity(owner_entity, ArmyRoster)
        except KeyError:
            return
        if not roster.regiment_entities:
            return
        alias_map = {
            "infantry": ("infantry",),
            "cavalry": ("cavalry",),
            "ranged": ("ranged",),
        }
        activation_slot: int | None = None
        activation_gain = 0
        for slot, regiment_ent in enumerate(roster.regiment_entities):
            try:
                regiment: Regiment = self.world.component_for_entity(regiment_ent, Regiment)
            except KeyError:
                continue
            unit_type = regiment.unit_type
            aliases = alias_map.get(unit_type)
            if not aliases:
                continue
            gained = sum(gains.get(alias, 0) for alias in aliases)
            if not gained:
                continue
            regiment.battle_readiness += gained
            if gained >= 3:
                if activation_slot is None or gained > activation_gain:
                    activation_slot = slot
                    activation_gain = gained
        if activation_slot is not None and activation_slot != roster.active_index:
            if 0 <= activation_slot < len(roster.regiment_entities):
                roster.active_index = activation_slot
