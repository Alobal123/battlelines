# AI Coding Agent Instructions – Battlelines

## Current Stack & Goals
Python 3.11+, Arcade (graphics/window loop), Esper (ECS), Blinker (event signals). Design a strongly component-driven, event-focused tactical game. Keep logic decoupled: components hold data only, systems implement behavior, events coordinate cross-system communication.

## Core Directories
src/ecs/components  dataclass components (Position, etc.)
src/ecs/systems     systems that iterate entities and/or react to events
src/ecs/events      event bus + event name registry
src/ecs/world.py    world factory (create_world)
src/main.py         entry point (Arcade Window + system wiring)
tests/              pytest tests mirroring src structure

## ECS Conventions
Components: pure data (no heavy logic). Add new component as a dataclass in its own file.
Systems: expose process() for frame-based iteration AND may subscribe to EventBus signals for async/event-driven updates.
World Creation: extend create_world() to register systems/factories; do NOT instantiate systems inside components.
Entity Creation: use helper factory (to add) — add a future module `ecs/factories.py` if patterns emerge.

## Event-Driven Pattern
Central EventBus (blinker's Signal) in `ecs/events/bus.py`.
Define event names as constants (e.g. EVENT_TICK, EVENT_SPAWN). Add new names in a single place to avoid fragmentation.
Emit events from systems or main loop instead of calling other systems directly.
Prefer payload dicts with primitive types or component instances; avoid passing World to handlers.
Input processing belongs in `InputSystem` translating raw mouse presses (EVENT_MOUSE_PRESS) to semantic game events (EVENT_TILE_CLICK).

## Frame Flow (Target Design)
Arcade window on_draw -> RenderSystem.process()
Scheduled tick (future: on_update or Arcade clock) emits EVENT_TICK -> subscribed systems react.
User input (future) -> translates to ACTION events (e.g. EVENT_MOVE_COMMAND) consumed by movement / AI systems.

## Adding New Logic (Checklist)
1. Create component dataclass (if new data needed).
2. Add system file with class receiving (world, event_bus, window?). Subscribe to relevant events in __init__.
3. Register system in main window or create_world (choose one consistent place; prefer window for access to rendering context, world factory for pure systems).
4. Emit events instead of direct cross-system method calls.
5. Add test: event subscription + component/system interaction (mirror path in tests/).

## Tests
Keep tests deterministic. For event dispatch tests: subscribe, emit, assert payload consumed.
Use conftest.py to ensure src on sys.path (already present). Add fixture factories as complexity grows.

## Performance Notes
Favor sparse systems (iterate only relevant components). Use world.get_component(Component) not raw entity lists.
Batch events if high-frequency (consider queue + flush each tick) once profiling shows need.

## Documentation Upkeep
Update README when adding: new systems, major events, run/test commands.
Create docs/ARCHITECTURE.md once >3 systems exist (render, movement, AI, spawn, etc.).

## Style & Quality
Type hints everywhere. Dataclasses for components. Avoid circular imports by keeping cross-cutting constants (events) isolated.
No hidden globals; pass EventBus explicitly.

## Next Recommended Steps (for agents)
Implement tick loop (Arcade on_update) emitting EVENT_TICK.
Add Movement component + MovementSystem reacting to EVENT_TICK and input events.
Render basic shapes for Position in RenderSystem.
Introduce factories module for entity creation.

## Match-Three Prototype Notes
BoardSystem initializes 8x8 grid (BoardCell + TileColor) with 7-color palette.
RenderSystem draws grid bottom-center; selection highlighted with white outline.
Mouse clicks -> EVENT_TILE_CLICK -> BoardSystem handles selection or swap (adjacent only).
Events emitted: EVENT_TILE_SELECTED, EVENT_TILE_SWAP_REQUEST, EVENT_TILE_SWAP_VALID/INVALID (MatchSystem), EVENT_TILE_SWAP_DO (logical swap), EVENT_TILE_SWAP_FINALIZE.
MatchSystem predicts swap validity (virtual swap + line scan) before animation begins. RenderSystem only animates after VALID/INVALID; invalid swaps animate forward then reverse without logical swap.
Phased animation flow:
1. Swap finalize -> MatchResolutionSystem detects matches and emits EVENT_MATCH_FOUND and EVENT_MATCH_CLEAR_BEGIN (no logical clear yet).
2. RenderSystem fades matched tiles; when fade completes it emits EVENT_MATCH_FADE_COMPLETE.
3. MatchResolutionSystem performs logical clear, computes gravity moves, emits EVENT_MATCH_CLEARED, EVENT_GRAVITY_MOVES and EVENT_GRAVITY_APPLIED.
4. RenderSystem animates falling; on completion emits EVENT_GRAVITY_SETTLED.
5. MatchResolutionSystem refills and emits EVENT_REFILL_COMPLETED; RenderSystem animates new tiles dropping from above.
Multiple cascades not yet implemented (single pass). Next: implement multi-cascade loop (repeat detection until stable), add scoring system (EVENT_SCORE_GAINED), visual polish (particle effects, combo indicators).

## Ask Before
Changing stack, adding networking, persisting data, or introducing heavy frameworks beyond current lightweight ECS/event setup.

