"""
ui.py

Tkinter layout and widget wiring. Owns ONLY presentation — it calls
into actions.py / state.py to do real work, and never the reverse.

Layout (single window, grid-based):
    +---------------------+------------------+
    |  stats panel (TL)   |  menu buttons     |
    |                     |  (TR, top-down)   |
    |     scene image (top-middle)            |
    +------------------------------------------+
    |  scrollable action list (bottom)         |
    |  each row: "<label>  —  <time cost>"     |
    +------------------------------------------+

Phase 1 (skeleton):
- Build the static grid layout with placeholder widgets.
- Stats panel shows dummy/hardcoded values.
- Middle image is a placeholder static image (assets/images/).
- Menu buttons (top-right) exist but are inert (print to console).
- Bottom action list has 2-3 dummy buttons that print to console
  when clicked. This proves the layout before any game logic exists.

Phase 2+: wire action buttons to actions.py, refresh stats panel and
image after each action resolves, update the bottom list from
get_available_actions(state).
"""

# TODO (Phase 1): build the Tkinter root window + grid frames described
#   above. Keep refresh_ui(state) as a single function that redraws
#   stats/image/action list from the current GameState, so later phases
#   just need to call it after state changes.
