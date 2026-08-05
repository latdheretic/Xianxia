# Project: Xianxia Cultivation Simulator (working title)

## Overview
Turn-based simulation RPG in the xianxia cultivation genre. Single-player,
local, native Linux desktop app. No real-time elements — everything advances
by player-chosen actions that consume in-game time (from instant to months).

## Tech stack
- Python 3 (stdlib only where possible)
- Tkinter for UI
- Pillow — the one third-party dependency. Not for formats (Tk 8.6 reads
  PNG natively) but for *resampling*: `tk.PhotoImage` can only rescale by
  whole-number ratios with nearest-neighbour sampling, which is too slow
  and too ugly to fit art to an arbitrary window size. See
  requirements.txt. The game degrades gracefully without it.
- JSON for save files (human-readable, easy to debug/patch by hand)
- No external game engine, no network, no database

## Assets & data
- `images/system/` — chrome that belongs to the game itself (menu
  backgrounds etc.); see the README there for ratio/cropping rules.
- Scene/location art gets its own home under `images/` in Phase 4.
- `data/cultivation.json` — realm ladders, resource ceilings and recovery
  rules. Tunable values belong here rather than in code; state.py only
  knows how to read and validate the file.

## Layout (Tkinter grid, single window)
- Top-left: player stats panel (name, stage, health, qi, spirit stones);
  click it for the full character sheet screen
- Top-middle: single static image for current scene/location
- Top-right: time block (always visible) above a context block, which
  shows either the location or the character being interacted with
- Middle: last action result, full width
- Bottom: scrollable list of available actions, each labeled with its
  time cost (e.g. "Meditate at the spring — 1 month"), with Main Menu
  anchored bottom-right

## Time & calendar (decided)
- 12 months of 30 days = 360-day years. Months are named for the zodiac
  starting at the Tiger, so the year turns over on the first month of
  spring (Tiger 1).
- Only months carry a zodiac animal. Years are numbered by the Imperial
  Era alone — naming the year as well read as clutter in the time panel.
  A run's starting year is rolled between 500 and 1500.
- Days run on whole hours, no minutes or seconds; anything under an hour
  is instant as far as the clock is concerned. Displayed on a 12-hour
  clock ("6:00 AM"), stored as 0-23.
- Actions cost either hours (up to 48) or whole days (3+). A day-costed
  action leaves the character starting again at the day start hour (6:00),
  which is also where a new run begins.
- The journey is tracked separately from the calendar, as elapsed days and
  completed years from the run's first day, so it survives those hour
  resets. It reads as a duration ("You have been cultivating for 1 day and
  4 years"); either half drops out at zero, so the first year shows only
  days and an exact anniversary shows only years. The sole exception is
  day one, which would otherwise have nothing left to print.
- The time panel shows two lines: the clock and date on one, the journey
  duration on the other. The era year lives on the character sheet, to
  keep the panel short.

## Cultivation (decided)
Four tracks advance in parallel, each with its own resource:

| Track | Resource | Resource ceiling | Recovery |
|---|---|---|---|
| Body Tempering | Stamina | 100 + progress | full in 2 hours |
| Qi Cultivation | Qi | 10 x progress | full in 1 week; qi cycling drives it x20 |
| Spirit Cultivation | Shen | 5 x progress | a night's sleep, or any action of 24h+ |
| Soul Cultivation | Karma | 100 x progress | never with time — events only |

- **The realm ladders live in `data/cultivation.json`, not in code.** Realm
  names and their progress ranges, the resource ceilings and the recovery
  rules all come from that file, so tuning the numbers never means editing
  state.py. The file is required — a missing or malformed one raises with
  a specific complaint rather than falling back to buried defaults, since
  silent defaults would hide a typo in the data.
- Progress is an integer starting at 0. Realms are contiguous ranges,
  1000 wide by default: 0-999, 1000-1999, and so on.
- The realm name is all the main screen shows. The character sheet adds
  the raw value, the range it sits in, and how far through it that is.
- Progress cannot leave its realm by itself: it stops at the top of the
  range, and only a breakthrough carries a cultivator over. The character
  sheet shows that state as exactly 100.0%. At the top of a ladder a
  breakthrough fails — define another realm in the data file to go on.
- Resource ceilings follow from progress, so cultivating widens the pool.
  Only body tempering starts anyone with a usable pool; the other three
  read 0 / 0 until that track is cultivated at all.
- Actions resolve as spend time -> apply effect -> recover. Recovery comes
  last on purpose: an action that deepens a track raises that resource's
  ceiling, and the time it took should fill the new pool, not the old one.

**Power level** is derived, not stored: the highest of the four progress
values plus the average of the other three, rounded to the nearest whole
number. Depth counts for more than breadth, and a single track carries a
cultivator on its own. It heads the cultivation block on both the side
panel and the character sheet, since it summarises the tracks under it.
Later it drives technique strength, and hostile locations will advertise
their own so the player can judge a fight before taking it.

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

## Save model (decided)
Roguelike mentality: any risk you take could end a run, and the save
file reflects that. State is persistent and written automatically after
every resolved action — there is no manual Save command in the UI. The
main menu is an in-window screen (never a popup) offering Continue Game
(back to the run in progress), Load Game (pick any run in the save
directory), New Game and Exit.

## Open questions / decide later
- Save file location: `save_data/` in project dir, or XDG-style
  `~/.local/share/<gamename>/`?
- Do actions *spend* their track's resource, not just recover it? Nothing
  drains stamina/qi/shen today. Stamina refills in two hours, so any cost
  on an hour-long action is invisible by the time the player looks — a
  cost model needs to account for that rather than be bolted on.
- What triggers a breakthrough? The bottleneck and GameState.breakthrough()
  exist, but nothing in the game calls it yet.
- How does Karma come back? It has no natural recovery by design, so the
  events that restore it are the only source.
- Interruption mechanic design (Phase 5) — not needed yet, just keep
  actions structured so it can be retrofitted.

## Explicitly out of scope for now
- Any real-time/animation elements
- Sound
- Multiplayer/networking
- Anything beyond static image + buttons for graphics
