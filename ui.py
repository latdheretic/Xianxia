"""
ui.py

Tkinter layout and widget wiring. Owns ONLY presentation — it calls
into actions.py / state.py to do real work, and never the reverse.

Layout (single window, grid-based):
    +---------------------+------------------+------------------+
    |  stats panel (TL)   |  scene image (TM)  |  menu (TR)     |
    +---------------------+------------------+------------------+
    |  last action result (full width)                          |
    +--------------------------------------------------------------+
    |  scrollable action list (bottom)                            |
    |  each row: "<label>  —  <time cost>"                        |
    +--------------------------------------------------------------+

Phase 1 (this file): static layout, dummy stats/state, inert action
buttons that print to console and echo a canned line into the result
box. Stats panel is clickable and opens a detail popup. Menu button
opens a popup with Save/Load/Quit stubs (Quit is real; the app has
nowhere to save to yet).

Phase 2+: wire action buttons to actions.py, refresh stats panel and
scene image after each action resolves via a single refresh_ui(state)
entry point, and populate the action list from
get_available_actions(state) instead of DUMMY_ACTIONS.
"""

import tkinter as tk
from tkinter import ttk

DUMMY_ACTIONS = [
    ("Travel to the village", "2 days"),
    ("Rest", "8 hours"),
    ("Meditate at the spring", "1 month"),
    ("Harvest spirit herbs", "4 hours"),
    ("Spar with a fellow disciple", "1 hour"),
    ("Browse the market stalls", "instant"),
]


def build_ui(root, state):
    root.title("Xianxia Cultivation Sim")
    root.geometry("960x680")
    root.minsize(800, 560)

    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=2)
    root.columnconfigure(2, weight=1)
    root.rowconfigure(0, weight=0)
    root.rowconfigure(1, weight=0)
    root.rowconfigure(2, weight=1)

    _build_stats_panel(root, state).grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
    _build_scene_panel(root, state).grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
    _build_menu_panel(root).grid(row=0, column=2, sticky="nsew", padx=6, pady=6)

    result_text = _build_result_box(root, state)
    result_text.grid(row=1, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 6))

    _build_action_list(root, result_text).grid(
        row=2, column=0, columnspan=3, sticky="nsew", padx=6, pady=(0, 6)
    )


def _build_stats_panel(root, state):
    frame = ttk.LabelFrame(root, text="Stats (click for details)")

    rows = [
        ("Name", state.name),
        ("Stage", state.stage),
        ("Date", state.date_str),
        ("Health", f"{state.health} / {state.max_health}"),
        ("Qi", f"{state.qi} / {state.max_qi}"),
        ("Spirit Stones", str(state.currency)),
    ]
    for i, (label, value) in enumerate(rows):
        ttk.Label(frame, text=f"{label}:").grid(row=i, column=0, sticky="w", padx=4, pady=1)
        ttk.Label(frame, text=value).grid(row=i, column=1, sticky="w", padx=4, pady=1)

    _bind_click_recursive(frame, lambda event: _open_stat_details(root, state))
    return frame


def _bind_click_recursive(widget, callback):
    widget.bind("<Button-1>", callback)
    for child in widget.winfo_children():
        _bind_click_recursive(child, callback)


def _open_stat_details(root, state):
    popup = tk.Toplevel(root)
    popup.title("Character Sheet")
    popup.geometry("320x340")

    rows = [
        ("Name", state.name),
        ("Cultivation Stage", state.stage),
        ("Age", str(state.age)),
        ("Health", f"{state.health} / {state.max_health}"),
        ("Qi", f"{state.qi} / {state.max_qi}"),
        ("Spirit Stones", str(state.currency)),
        ("Location", state.location),
        ("Date", state.date_str),
    ]
    for i, (label, value) in enumerate(rows):
        ttk.Label(popup, text=f"{label}:").grid(row=i, column=0, sticky="w", padx=8, pady=4)
        ttk.Label(popup, text=value).grid(row=i, column=1, sticky="w", padx=8, pady=4)

    ttk.Button(popup, text="Close", command=popup.destroy).grid(
        row=len(rows), column=0, columnspan=2, pady=8
    )


def _build_scene_panel(root, state):
    frame = ttk.LabelFrame(root, text="Scene")
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)

    subject = state.interacting_with or state.location
    canvas = tk.Canvas(frame, width=320, height=280, background="#3a3a3a", highlightthickness=0)
    canvas.create_text(
        160, 140, text=f"[{subject}]", fill="white", width=280, justify="center"
    )
    canvas.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
    return frame


def _build_menu_panel(root):
    frame = ttk.LabelFrame(root, text="Menu")
    ttk.Button(frame, text="Main Menu", command=lambda: _open_main_menu(root)).pack(
        padx=8, pady=8
    )
    return frame


def _open_main_menu(root):
    popup = tk.Toplevel(root)
    popup.title("Main Menu")
    popup.geometry("240x220")

    ttk.Button(popup, text="Resume", command=popup.destroy).pack(fill="x", padx=12, pady=6)
    ttk.Button(
        popup, text="Save Game", command=lambda: print("[stub] Save game clicked")
    ).pack(fill="x", padx=12, pady=6)
    ttk.Button(
        popup, text="Load Game", command=lambda: print("[stub] Load game clicked")
    ).pack(fill="x", padx=12, pady=6)
    ttk.Button(
        popup,
        text="Load Different Game",
        command=lambda: print("[stub] Load different game clicked"),
    ).pack(fill="x", padx=12, pady=6)
    ttk.Button(popup, text="Quit to Desktop", command=root.destroy).pack(
        fill="x", padx=12, pady=6
    )


def _build_result_box(root, state):
    text = tk.Text(root, height=3, wrap="word", state="disabled")
    _set_result_text(text, state.last_action_result)
    return text


def _set_result_text(text_widget, message):
    text_widget.configure(state="normal")
    text_widget.delete("1.0", "end")
    text_widget.insert("1.0", message)
    text_widget.configure(state="disabled")


def _build_action_list(root, result_text):
    outer = ttk.LabelFrame(root, text="Actions")
    outer.rowconfigure(0, weight=1)
    outer.columnconfigure(0, weight=1)

    canvas = tk.Canvas(outer, highlightthickness=0)
    scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)

    inner.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")

    for label, time_cost in DUMMY_ACTIONS:
        _add_action_button(inner, label, time_cost, result_text)

    return outer


def _add_action_button(parent, label, time_cost, result_text):
    button = ttk.Button(
        parent,
        text=f"{label}  —  {time_cost}",
        command=lambda: _on_action_clicked(label, time_cost, result_text),
    )
    button.pack(fill="x", padx=4, pady=2)


def _on_action_clicked(label, time_cost, result_text):
    message = (
        f"[dummy] You chose to {label.lower()} ({time_cost}). "
        "Nothing happens yet — actions.py isn't wired up."
    )
    print(message)
    _set_result_text(result_text, message)
