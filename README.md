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
(Initial window opens; rendering logic minimal.)

## Tests
```powershell
pytest -q
```
(Add pytest to requirements as soon as testing expands.)

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
1. Add a ticking game loop emitting `tick` events.
2. Implement rendering of positions with Arcade shapes.
3. Add movement system responding to input events.
4. Introduce entity factory utilities.

## Event Reference (Selected)
Key gameplay events emitted by systems:
- `tile_swap_request` / `tile_swap_do` / `tile_swap_finalize`: Swap lifecycle.
- `match_found` / `match_cleared`: Detection and logical clearing of matches.
- `gravity_applied` / `refill_completed`: Board settling and new tile spawn.
- `cascade_step` / `cascade_complete`: Multi-step resolution depth tracking.
- `ability_activate_request` / `ability_target_mode` / `ability_target_selected` / `ability_effect_applied`: Ability targeting & resolution.
- `tile_bank_spend_request` / `tile_bank_spent` / `tile_bank_insufficient` / `tile_bank_changed`: Resource economy.
- `turn_advanced`: Emitted by `TurnSystem` whenever active owner changes (payload: previous_owner, new_owner). Use this for UI updates instead of polling `ActiveTurn`.

See `ecs/events/bus.py` for the full list.

## License
TBD
