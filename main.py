"""
main.py

Entry point. Loads or creates GameState, launches the Tkinter UI, and
wires action dispatch between ui.py and actions.py/state.py.

Phase 1: just instantiate the UI with a dummy state and start the
Tkinter mainloop.
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
