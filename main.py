"""
main.py

Entry point. Loads or creates GameState, launches the Tkinter UI, and
wires action dispatch between ui.py and actions.py/state.py.

Phase 1: instantiate the UI with a placeholder state and start the
Tkinter mainloop. The game boots into the main menu, and the state
handed over here is only what the main screen is sized against until
New Game (or, from Phase 3, Load Game) supplies a real run.

Phase 2: dispatch_action() is the seam between the UI and the rules —
the UI reports which action was clicked and knows nothing about what it
does; actions.py resolves it against the state. Phase 3 hangs autosave
off the same function, since every resolved action is exactly when a run
should be written back to disk.
"""

import tkinter as tk

from state import GameState
from ui import build_ui


def dispatch_action(state, action):
    """Resolve one clicked action. Returns the line for the result box."""
    message = action.resolve(state)
    # TODO (Phase 3): autosave(state) belongs here — after the action has
    #   resolved, before the player can take another.
    return message


def main():
    state = GameState.new_game()
    root = tk.Tk()
    build_ui(root, state, dispatch_action)
    root.mainloop()


if __name__ == "__main__":
    main()
