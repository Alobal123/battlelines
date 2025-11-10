from dataclasses import dataclass


@dataclass(slots=True)
class EffectExpireOnEvents:
    """Metadata describing which events should terminate the owning effect."""

    events: tuple[str, ...]
    match_owner: bool = False
    payload_owner_key: str = "owner_entity"
