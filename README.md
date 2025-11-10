# Battlelines

Experimental tactical / strategy game using Python, Arcade, and ECS (Esper) with an event-driven architecture.

## Stack
- Python 3.11+
- Arcade (graphics/windowing)
- Esper (ECS framework)
- Blinker (event signals)

## Setup
```powershell
python -m venv .venv
. .venv/Scripts/Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Running
```powershell
python src/main.py
```
(Arcade window opens with current board/ability UI.)

## Tests
```powershell
pytest -q
```

## Project Layout
```
src/
  main.py              # entry point
  ecs/
    world.py           # world factory
    events/bus.py      # event bus abstraction
    components/        # dataclass components (Position, etc.)
    systems/           # systems (RenderSystem, etc.)
```

## Conventions
- Components: lightweight dataclasses in `ecs/components`; no methods beyond trivial helpers.
- Systems: process logic + optional event subscriptions; avoid direct coupling between systems (communicate via events).
- Events: define names centrally in `ecs/events/bus.py` or future `events/registry.py`.
- No global state; pass EventBus and World explicitly.

## Next Steps
1. Promote the scheduled `on_update` hook in `BattlelinesWindow` to emit `EVENT_TICK` and migrate systems that currently poll inside `process`.
2. Add a movement/command system that reacts to semantic events from `InputSystem` and drives board interactions beyond swaps.
3. Introduce entity factories (`ecs/factories.py`) for scenario setup to keep tests and future content authoring tidy.
4. Sketch high-level architecture notes (`docs/ARCHITECTURE.md`) once additional systems land (movement/AI/battle outcome).

## Ability Flow
Ability control now spans three lightweight systems:

- `AbilityTargetingSystem` manages activation requests and gathers targeting input while locking out cascades.
- `AbilityActivationSystem` listens for `EVENT_TILE_BANK_SPENT`, marks the turn action as started, and re-emits the confirmed payload as `EVENT_ABILITY_EXECUTE`.
- `AbilityResolutionSystem` handles `EVENT_ABILITY_EXECUTE`, looks up the matching resolver (see `ecs/systems/abilities/`), and emits `EVENT_ABILITY_EFFECT_APPLIED` after the effect resolves.

Resolvers live in `ecs/systems/abilities/` with plugin discovery consolidated in `abilities/registry.py`. Each resolver receives an `AbilityContext` containing the pending targeting data, world, and event bus.

## Event Reference (Selected)
Key gameplay events emitted by systems:
- `tile_swap_request` / `tile_swap_do` / `tile_swap_finalize`: Swap lifecycle.
- `match_found` / `match_cleared`: Detection and logical clearing of matches.
- `gravity_applied` / `refill_completed`: Board settling and new tile spawn.
- `cascade_step` / `cascade_complete`: Multi-step resolution depth tracking.
- `ability_activate_request` / `ability_target_mode` / `ability_target_selected` / `ability_execute` / `ability_effect_applied`: Ability targeting & resolution.
- `tile_bank_spend_request` / `tile_bank_spent` / `tile_bank_insufficient` / `tile_bank_changed`: Resource economy.
- `turn_action_started`: Fired when any turn-level action (swap, ability, etc.) kicks off; pairs with `turn_advanced` for UI state machines.
- `turn_advanced`: Emitted by `TurnSystem` whenever active owner changes (payload: previous_owner, new_owner). Use this for UI updates instead of polling `ActiveTurn`.

See `ecs/events/bus.py` for the full list.

## License
TBD
