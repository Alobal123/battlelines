"""Enemy factory helpers."""

from .undead_beekeeper import (
    DEFAULT_UNDEAD_BEEKEEPER_LOADOUT,
    create_enemy_undead_beekeeper,
)
from .undead_florist import (
    DEFAULT_UNDEAD_FLORIST_LOADOUT,
    create_enemy_undead_florist,
)
from .undead_gardener import (
    DEFAULT_UNDEAD_GARDENER_LOADOUT,
    create_enemy_undead_gardener,
)
from .bloodhound import (
    DEFAULT_BLOODHOUND_LOADOUT,
    create_enemy_bloodhound,
)
from .codex import (
    DEFAULT_CODEX_LOADOUT,
    create_enemy_codex,
)
from .grimoire import (
    DEFAULT_GRIMOIRE_LOADOUT,
    create_enemy_grimoire,
)
from .kennelmaster import (
    DEFAULT_KENNELMASTER_LOADOUT,
    create_enemy_kennelmaster,
)
from .librarian import (
    DEFAULT_LIBRARIAN_LOADOUT,
    create_enemy_librarian,
)
from .mastiffs import (
    DEFAULT_MASTIFFS_LOADOUT,
    create_enemy_mastiffs,
)

__all__ = [
    "DEFAULT_UNDEAD_BEEKEEPER_LOADOUT",
    "create_enemy_undead_beekeeper",
    "DEFAULT_UNDEAD_GARDENER_LOADOUT",
    "create_enemy_undead_gardener",
    "DEFAULT_UNDEAD_FLORIST_LOADOUT",
    "create_enemy_undead_florist",
    "DEFAULT_BLOODHOUND_LOADOUT",
    "create_enemy_bloodhound",
    "DEFAULT_KENNELMASTER_LOADOUT",
    "create_enemy_kennelmaster",
    "DEFAULT_MASTIFFS_LOADOUT",
    "create_enemy_mastiffs",
    "DEFAULT_GRIMOIRE_LOADOUT",
    "create_enemy_grimoire",
    "DEFAULT_CODEX_LOADOUT",
    "create_enemy_codex",
    "DEFAULT_LIBRARIAN_LOADOUT",
    "create_enemy_librarian",
]
