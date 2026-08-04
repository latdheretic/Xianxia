"""
main.py

Entry point. Loads or creates GameState, launches the Tkinter UI, and
wires action dispatch between ui.py and actions.py/state.py.

Phase 1: instantiate the UI with a placeholder state and start the
Tkinter mainloop. The game boots into the main menu, and the state
handed over here is only what the main screen is sized against until
New Game (or, from Phase 3, Load Game) supplies a real run.
"""

import tkinter as tk

from state import GameState
from ui import build_ui


def main():
    state = GameState.new_game()
    root = tk.Tk()
    build_ui(root, state)
    root.mainloop()


if __name__ == "__main__":
    main()
