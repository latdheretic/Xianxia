# Project: Xianxia Cultivation Sim (working title)

## Overview
Turn-based simulation RPG in the xianxia cultivation genre. Single-player,
local, native Linux desktop app. No real-time elements — everything advances
by player-chosen actions that consume in-game time (from instant to months).

## Tech stack
- Python 3 (stdlib only where possible)
- Tkinter for UI (Pillow only if we need image formats beyond PNG/GIF)
- JSON for save files (human-readable, easy to debug/patch by hand)
- No external game engine, no network, no database

## Layout (Tkinter grid, single window)
- Top-left: stats panel (name, cultivation stage, qi, health, age, etc.)
- Top-middle: single static image for current scene/location
- Top-right: menu buttons (Save, Load, Character Sheet, Inventory, etc.)
- Bottom: scrollable list of available actions, each labeled with its
  time cost (e.g. "Meditate at the spring — 1 month")

## Core loop
1. Game state loaded (or new game created) on launch.
2. Available actions are generated based on current location/state.
3. Player clicks an action -> action resolves -> game clock advances by
   that action's time cost -> stats/world update -> UI refreshes.
4. Autosave after every action (or on a timer — TBD, see Open Questions).

## Build phases (do NOT skip ahead — each phase should be independently
testable before starting the next)
1. **Skeleton** — static window layout, dummy stats, 2-3 buttons that just
   print to console. No game logic.
2. **Time & stats** — game clock advances on action; stats update from a
   small set of hardcoded test actions (no procedural content yet).
3. **Save/load** — JSON serialization of game state from Phase 2. Keep the
   schema minimal and versioned (see save_data/schema_notes.md).
4. **Procedural generation** — world/location generation feeds the action
   list dynamically as new areas/events are discovered.
5. **Polish / expansion hooks** — interruption mechanics for long/loud
   actions, random events, etc. NOT part of the initial build — the action
   system should be designed so this can be added later without a rewrite
   (each action already models "time cost -> resolution effect"; an
   interrupt is just a check inserted mid-resolution).

## Module responsibilities
- `state.py` — GameState class, player stats, world state, save/load
- `generation.py` — procedural world/event/content generation
- `actions.py` — action definitions, time costs, resolution effects
- `ui.py` — Tkinter layout, widget wiring, refresh logic
- `main.py` — entry point, ties modules together, dispatches actions

## Conventions
- Keep UI code (`ui.py`) decoupled from game logic — UI calls into
  `actions.py`/`state.py`, never the reverse. This keeps diffs small when
  iterating on one layer at a time.
- Game state should be a single serializable object/dict tree — avoid
  scattering state across globals.
- Prefer explicit, small functions over cleverness — this keeps token
  costs down when asking Claude Code to modify specific behavior later.

## Open questions / decide later
- Autosave: every action vs. every N in-game days vs. manual save only?
- Save file location: `save_data/` in project dir, or XDG-style
  `~/.local/share/<gamename>/`?
- Interruption mechanic design (Phase 5) — not needed yet, just keep
  actions structured so it can be retrofitted.

## Explicitly out of scope for now
- Any real-time/animation elements
- Sound
- Multiplayer/networking
- Anything beyond static image + buttons for graphics
