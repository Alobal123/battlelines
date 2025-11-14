# Battlelines

Experimental tactical puzzle battler built with Python, Arcade, and an event-driven ECS (Esper).

## Stack
- Python 3.11+
- Arcade (graphics/windowing)
- Esper (ECS framework)
- Blinker (event signals)

## Setup
```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Running
```powershell
python -m src.main
```
Launches the Arcade window with the current board and UI wiring.

## Tests
```powershell
python -m pytest
```

## Project Layout
```
src/
  main.py              # entry point
  ecs/
    world.py           # world factory
    events/bus.py      # event bus abstraction
    components/        # dataclass components (Position, etc.)
  systems/           # gameplay systems (board, abilities, rendering, etc.)
```

## Conventions
- Components: lightweight dataclasses in `ecs/components`; no methods beyond trivial helpers.
- Systems: logic lives here; most subscribe to events rather than iterating every frame. Per-effect systems sit in `ecs/systems/effects/`.
- Events: define names centrally in `ecs/events/bus.py` and emit signals instead of direct cross-system calls.
- No global state; pass EventBus and World explicitly.

## Next Steps
1. Add a movement/command system that reacts to semantic events from `InputSystem` so the board can process orders beyond swaps.
2. Flesh out rendering overlays (unit highlights, ability affordances) using cached sprite layout data.
3. Introduce entity factories (`ecs/factories.py`) for deterministic scenario setup shared by tests and content creation.
4. Capture multi-system wiring in `docs/ARCHITECTURE.md` once movement and AI layers join the build.

## Ability Flow
Ability control now spans three lightweight systems:

- `AbilityTargetingSystem` manages activation requests and gathers targeting input while locking out cascades.
- `AbilityActivationSystem` listens for `EVENT_TILE_BANK_SPENT`, marks the turn action as started, and re-emits the confirmed payload as `EVENT_ABILITY_EXECUTE`.
- `AbilityResolutionSystem` handles `EVENT_ABILITY_EXECUTE`, looks up the matching resolver (see `ecs/systems/abilities/`), and emits `EVENT_ABILITY_EFFECT_APPLIED` after the effect resolves.

Resolvers live in `ecs/systems/abilities/` with plugin discovery consolidated in `abilities/registry.py`. Each resolver receives an `AbilityContext` containing the pending targeting data, world, and event bus.

## Effect Processing
Every active effect is a dedicated entity managed by `EffectLifecycleSystem`. Immediate payloads such as damage and healing are routed through per-effect systems in `ecs/systems/effects/` that listen for `EVENT_EFFECT_APPLIED` / `EVENT_EFFECT_REFRESHED`, emit the relevant health event, and retire the effect entity once resolved.

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
