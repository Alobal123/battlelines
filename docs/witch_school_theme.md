# Witch School Theme (Transition Plan)

We are re-theming the game from army/regiment combat to a magical academy setting.
This document outlines the mapping of old concepts to new ones and incremental steps.

## Concept Mapping
| Old (Army)        | New (Witch School) | Notes |
|-------------------|--------------------|-------|
| Regiment          | House Circle / Coven Cell | Houses are long-lived; circles represent active groups for challenges. |
| ArmyRoster        | HouseRoster        | Tracks active study circle or duel participants. |
| Tile Types: infantry, ranged, cavalry, etc. | nature, blood, shapeshift, spirit, hex, secrets, witchfire | Replaced with magical faculties. |
| Ability (tactical_shift) | Spell (flux_shift) | Naming pass later. |
| TileBank (resource counts) | ManaPool / EssenceVault | Stores colored essences tied to faculty. |
| Effects (morale_boost) | Buffs (focus_boost, ward) | Morale becomes Focus/Ward. |

## New Magical Faculties
Current canonical set in `world.create_world`:
- nature (#3F7F3B)
- blood (#B3122A)
- shapeshift (#D89B26)
- spirit (#A58BEA)
- hex (#7B3E85)
- secrets (#E8D7A1)
- witchfire (#E23EA0)

These replace previous martial categories and will drive spell costs and board matching.

## Incremental Refactor Steps
1. Keep existing systems functional: Only tile type names swapped.
2. Introduce new components: `House`, `Circle`, `ManaPool` (wrapper around TileBank) – staged.
3. Rename abilities and effects to arcane vocabulary.
4. Update rendering layers: iconography, panel labels.
5. Remove legacy regiment stats once no system reads them.

## Event Renaming (Future)
- EVENT_ABILITY_EXECUTE -> EVENT_SPELL_RESOLVE
- EVENT_TILE_BANK_SPENT -> EVENT_MANA_POOL_SPENT

## Compatibility Notes
Tests referencing old tile type names will fail once removed. Keep old names in parallel or update tests synchronously.

## Open Questions
- Do houses have unique passive auras? (Could be an `Aura` component.)
- Should nature/blood/witchfire essences have rarity tiers affecting refill probabilities?

## Next Suggested Small Steps
- Create `components/house.py` (data: name, crest_color).
- Add `systems/house_progression_system.py` listening for SPELL_RESOLVE to grant experience.
- Migrate UI labels.

---
This file should evolve as the re-theme proceeds.
