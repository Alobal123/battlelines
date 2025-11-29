from typing import Dict

from esper import World
from ecs.events.bus import (
    EventBus,
    EVENT_TILES_MATCHED,
    EVENT_BANK_MANA,
    EVENT_TILE_BANK_CHANGED,
    EVENT_TILE_BANK_SPEND_REQUEST,
    EVENT_TILE_BANK_SPENT,
    EVENT_TILE_BANK_INSUFFICIENT,
    EVENT_EFFECT_APPLY,
)
from ecs.components.tile_bank import TileBank
from ecs.components.ability_list_owner import AbilityListOwner
from ecs.components.tile_type_registry import TileTypeRegistry
from ecs.components.tile_types import TileTypes

class TileBankSystem:
    """Tracks cleared tiles and manages spending for abilities.

    Logic:
      - On EVENT_TILES_MATCHED: increment counts for the owner's bank (assumes single player for now).
      - On EVENT_BANK_MANA: process external mana grants (knowledge bar, effects, etc.).
      - On EVENT_TILE_BANK_SPEND_REQUEST: validate and spend or emit insufficient.
        Assumptions:
            - Single player entity with AbilityListOwner; extend later for multiple players.
        Color is no longer processed here; semantic type names are the sole currency.
    """
    def __init__(self, world: World, event_bus: EventBus):
        self.world = world
        self.event_bus = event_bus
        self.event_bus.subscribe(EVENT_TILES_MATCHED, self.on_tiles_matched)
        self.event_bus.subscribe(EVENT_TILE_BANK_SPEND_REQUEST, self.on_spend_request)
        self.event_bus.subscribe(EVENT_BANK_MANA, self.on_bank_mana)

    def _get_or_create_bank(self, owner_entity: int) -> int:
        # Find existing bank for owner or create one.
        for ent, bank in self.world.get_component(TileBank):
            if bank.owner_entity == owner_entity:
                return ent
        bank_ent = self.world.create_entity(TileBank(owner_entity=owner_entity))
        return bank_ent

    def _list_owners(self) -> list:
        return [ent for ent, comp in self.world.get_component(AbilityListOwner)]

    def on_tiles_matched(self, sender, **kwargs):
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
            if not isinstance(type_name, str) or not type_name:
                continue
            bank.add(type_name, 1)
            readiness_gains[type_name] = readiness_gains.get(type_name, 0) + 1
        if readiness_gains:
            self._apply_readiness_from_tiles(owner_entity, readiness_gains)
            self._emit_bank_changed(
                bank_entity=bank_ent,
                owner_entity=owner_entity,
                counts=bank.counts.copy(),
                delta=readiness_gains,
                source=kwargs.get('source', 'tiles_matched'),
            )

        witchfire_cleared = readiness_gains.get('witchfire', 0)
        if witchfire_cleared:
            self._apply_witchfire_damage(owner_entity, witchfire_cleared)
        chaos_cleared = readiness_gains.get('chaos', 0)
        if chaos_cleared:
            self._apply_chaos_damage(owner_entity, chaos_cleared)

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
            spent_delta = {k: -int(v) for k, v in cost.items() if int(v)}
            if spent_delta:
                self._emit_bank_changed(
                    bank_entity=bank_ent,
                    owner_entity=owner_entity,
                    counts=bank_obj.counts.copy(),
                    delta=spent_delta,
                    source='tile_bank_spend',
                    ability_entity=ability_entity,
                )

    def on_bank_mana(self, sender, **kwargs):
        owner_entity = kwargs.get('owner_entity')
        if owner_entity is None:
            return
        gains_payload = kwargs.get('gains')
        gains: Dict[str, int] = {}
        if isinstance(gains_payload, dict):
            for key, value in gains_payload.items():
                amount_int = self._coerce_positive(value)
                if amount_int > 0 and isinstance(key, str) and key:
                    gains[key] = gains.get(key, 0) + amount_int
        else:
            type_name = kwargs.get('type_name')
            amount_int = self._coerce_positive(kwargs.get('amount', 1), default=1)
            if isinstance(type_name, str) and type_name and amount_int > 0:
                gains[type_name] = amount_int
        if not gains:
            return
        bank_ent = self._get_or_create_bank(owner_entity)
        bank: TileBank = self.world.component_for_entity(bank_ent, TileBank)
        for type_name, amount in gains.items():
            bank.add(type_name, amount)
        delta = {
            type_name: int(amount)
            for type_name, amount in gains.items()
            if amount
        }
        self._emit_bank_changed(
            bank_entity=bank_ent,
            owner_entity=owner_entity,
            counts=bank.counts.copy(),
            delta=delta,
            source=kwargs.get('source', 'bank_mana'),
        )

    def process(self):
        # Not used per-frame currently
        return

    def _registry(self) -> TileTypes:
        for ent, _ in self.world.get_component(TileTypeRegistry):
            return self.world.component_for_entity(ent, TileTypes)
        raise RuntimeError('TileTypes definitions not found')

    def _apply_readiness_from_tiles(self, owner_entity: int, gains: Dict[str, int]) -> None:
        # Regiment readiness removed; placeholder for future House/Circle progression.
        return

    def _apply_witchfire_damage(self, clearing_owner: int, amount: int) -> None:
        """Emit damage events for each opponent when witchfire is cleared."""
        from ecs.components.health import Health
        opponents = [
            ent for ent, _ in self.world.get_component(Health)
            if ent != clearing_owner
        ]
        for opponent in opponents:
            self.event_bus.emit(
                EVENT_EFFECT_APPLY,
                owner_entity=opponent,
                source_entity=None,
                slug="damage",
                turns=0,
                metadata={
                    "amount": amount,
                    "reason": "witchfire",
                    "source_owner": clearing_owner,
                },
            )

    def _apply_chaos_damage(self, clearing_owner: int, amount: int) -> None:
        """Chaos backlash always targets the human player regardless of who matched it."""
        from ecs.components.human_agent import HumanAgent

        human_owner = None
        for ent, _ in self.world.get_component(HumanAgent):
            human_owner = ent
            break
        if human_owner is None:
            return
        self.event_bus.emit(
            EVENT_EFFECT_APPLY,
            owner_entity=human_owner,
            source_entity=None,
            slug="damage",
            turns=0,
            metadata={
                "amount": amount,
                "reason": "chaos",
                "source_owner": clearing_owner,
            },
        )

    def _emit_bank_changed(
        self,
        *,
        bank_entity: int,
        owner_entity: int,
        counts: Dict[str, int],
        delta: Dict[str, int],
        source: str,
        ability_entity: int | None = None,
    ) -> None:
        normalized_delta = {
            type_name: int(amount)
            for type_name, amount in (delta or {}).items()
            if int(amount) != 0
        }
        if not normalized_delta:
            return
        payload = {
            'entity': bank_entity,
            'owner_entity': owner_entity,
            'counts': counts,
            'delta': normalized_delta,
            'source': source,
        }
        if ability_entity is not None:
            payload['ability_entity'] = ability_entity
        self.event_bus.emit(EVENT_TILE_BANK_CHANGED, **payload)

    @staticmethod
    def _coerce_positive(value, *, default: int = 0) -> int:
        try:
            amount = int(value)
        except (TypeError, ValueError):
            return default
        return amount if amount > 0 else default
