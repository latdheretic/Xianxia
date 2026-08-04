"""
ui.py

Tkinter layout and widget wiring. Owns ONLY presentation — it calls
into actions.py / state.py to do real work, and never the reverse.

Layout (single window, grid-based):
    +---------------+-------------------------+----------------+
    |  player stats |                         |  world stats   |
    |  (click for   |    scene image           |  (or opponent  |
    |  details)     |    IMAGE_SIZE square     |  stats, if in  |
    |               |                         |  combat)       |
    +---------------+-------------------------+----------------+
    |  last action result (full width)                          |
    +--------------------------------------------------------------+
    |  scrollable action list             |  Main Menu (bottom-  |
    |  each row: "<label> — <time cost>"  |  right, fixed)       |
    +--------------------------------------------------------------+

Scale-to-fit + letterbox: the whole layout above ("content") is built
at a BASE_* pixel/font scale, measured once, then re-built at
scale = window_size / that base size on every resize. Content between
4:3 and 16:9 fills the window edge to edge (side panels absorb the
extra width, same as before). Outside that family — an ultrawide or
a very tall/narrow window — the content is capped at whichever of
4:3/16:9 it's approaching and centered, leaving blank window
background on the excess edges rather than distorting anything.
Scale is clamped to [MIN_SCALE, MAX_SCALE] as the "minimum/maximum
workable resolution"; root.minsize() keeps the window from ever being
shrunk past what MIN_SCALE needs.

Phase 1 (this file): static layout, dummy stats/state, inert action
buttons that print to console and echo a canned line into the result
box. Player stats panel is clickable and opens a detail popup. Main
Menu is just another bottom-row control (not a top corner button) so
it reads as one of the available choices, always anchored bottom-right
for consistency as the action list grows/shrinks.

Phase 2+: wire action buttons to actions.py, refresh stats panels and
scene image after each action resolves via a single refresh_ui(state)
entry point, and populate the action list from
get_available_actions(state) instead of DUMMY_ACTIONS.
"""

import tkinter as tk
from tkinter import ttk

MIN_RATIO = 4 / 3  # older 4:3 monitors
MAX_RATIO = 16 / 9  # standard widescreen

MIN_SCALE = 0.6  # minimum workable resolution floor
MAX_SCALE = 1.5  # don't blow fonts/elements up past this on huge displays

BASE_IMAGE_SIZE = 600
BASE_SIDE_PANEL_WIDTH = 260
BASE_ACTIONS_HEIGHT = 180
BASE_MENU_COLUMN_WIDTH = 150
BASE_PADDING = 6
BASE_FONT_SIZE = 12
FONT_FAMILY = "TkDefaultFont"

RESIZE_DEBOUNCE_MS = 120

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
    root.configure(background=ttk.Style().lookup("TFrame", "background"))

    base_width, base_height = _measure_natural_size(root, state)
    root.minsize(round(base_width * MIN_SCALE), round(base_height * MIN_SCALE))

    layout = {"content": None, "resize_job": None}

    def apply_layout(window_w, window_h):
        scale, content_width = _compute_scale_and_width(
            window_w, window_h, base_width, base_height
        )
        if layout["content"] is not None:
            layout["content"].destroy()
        content = _build_content(root, state, scale)
        content.place(relx=0.5, rely=0.5, anchor="center", width=content_width)
        layout["content"] = content

    def on_configure(event):
        if event.widget is not root:
            return
        if layout["resize_job"] is not None:
            root.after_cancel(layout["resize_job"])
        layout["resize_job"] = root.after(
            RESIZE_DEBOUNCE_MS,
            lambda: apply_layout(root.winfo_width(), root.winfo_height()),
        )

    root.bind("<Configure>", on_configure)
    root.geometry(f"{base_width}x{base_height}")
    apply_layout(base_width, base_height)


def _measure_natural_size(root, state):
    probe = _build_content(root, state, scale=1.0)
    probe.update_idletasks()
    width, height = probe.winfo_reqwidth(), probe.winfo_reqheight()
    probe.destroy()
    return width, height


def _compute_scale_and_width(window_w, window_h, base_width, base_height):
    """Pick a scale that fits the content in the window, and a width for it.

    Scale is a straight fit against the natural content size, so the layout
    is never squeezed below what it needs at that scale (which would clip
    labels). Width then stretches the side panels out to the window's own
    ratio, but only within the 4:3..16:9 family — a squarer or wider window
    keeps the content at the nearest supported ratio and leaves the excess
    as blank window background.
    """
    if window_h <= 0 or window_w <= 0:
        return MIN_SCALE, round(base_width * MIN_SCALE)

    scale = min(window_w / base_width, window_h / base_height)
    scale = min(max(scale, MIN_SCALE), MAX_SCALE)

    window_ratio = window_w / window_h
    target_ratio = min(max(window_ratio, MIN_RATIO), MAX_RATIO)

    natural_width = base_width * scale
    stretched_width = base_height * scale * target_ratio
    content_width = min(window_w, max(natural_width, stretched_width))
    return scale, round(content_width)


def _build_content(root, state, scale):
    font_size = max(6, round(BASE_FONT_SIZE * scale))
    font = (FONT_FAMILY, font_size)
    image_size = round(BASE_IMAGE_SIZE * scale)
    side_panel_width = round(BASE_SIDE_PANEL_WIDTH * scale)
    actions_height = round(BASE_ACTIONS_HEIGHT * scale)
    menu_column_width = round(BASE_MENU_COLUMN_WIDTH * scale)
    padding = max(2, round(BASE_PADDING * scale))

    content = ttk.Frame(root)
    content.columnconfigure(0, weight=1, minsize=side_panel_width)
    content.columnconfigure(1, weight=0, minsize=image_size)
    content.columnconfigure(2, weight=1, minsize=side_panel_width)

    # Values wrap rather than clip once a panel gets narrow at small scales.
    wrap = max(80, side_panel_width - round(90 * scale))

    _build_player_panel(content, root, state, font, wrap).grid(
        row=0, column=0, sticky="nsew", padx=padding, pady=padding
    )
    _build_scene_panel(content, state, image_size, font).grid(
        row=0, column=1, sticky="nsew", padx=padding, pady=padding
    )
    _build_right_panel(content, state, font, wrap).grid(
        row=0, column=2, sticky="nsew", padx=padding, pady=padding
    )

    result_text = _build_result_box(content, state, font)
    result_text.grid(row=1, column=0, columnspan=3, sticky="ew", padx=padding, pady=(0, padding))

    _build_bottom_section(
        content, root, result_text, font, actions_height, menu_column_width
    ).grid(row=2, column=0, columnspan=3, sticky="ew", padx=padding, pady=(0, padding))

    return content


def _build_player_panel(parent, root, state, font, wrap):
    frame = ttk.LabelFrame(parent, text="Player (click for details)")

    rows = [
        ("Name", state.name),
        ("Stage", state.stage),
        ("Health", f"{state.health} / {state.max_health}"),
        ("Qi", f"{state.qi} / {state.max_qi}"),
        ("Spirit Stones", str(state.currency)),
    ]
    _fill_stat_rows(frame, rows, font, wrap)

    _bind_click_recursive(frame, lambda event: _open_stat_details(root, state, font))
    return frame


def _fill_stat_rows(frame, rows, font, wrap):
    for i, (label, value) in enumerate(rows):
        ttk.Label(frame, text=f"{label}:", font=font).grid(
            row=i, column=0, sticky="nw", padx=4, pady=1
        )
        ttk.Label(frame, text=value, font=font, wraplength=wrap, justify="left").grid(
            row=i, column=1, sticky="w", padx=4, pady=1
        )


def _bind_click_recursive(widget, callback):
    widget.bind("<Button-1>", callback)
    for child in widget.winfo_children():
        _bind_click_recursive(child, callback)


def _open_stat_details(root, state, font):
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
        ttk.Label(popup, text=f"{label}:", font=font).grid(
            row=i, column=0, sticky="w", padx=8, pady=4
        )
        ttk.Label(popup, text=value, font=font).grid(row=i, column=1, sticky="w", padx=8, pady=4)

    ttk.Button(popup, text="Close", command=popup.destroy).grid(
        row=len(rows), column=0, columnspan=2, pady=8
    )


def _build_right_panel(parent, state, font, wrap):
    if state.in_combat:
        return _build_opponent_panel(parent, state, font, wrap)
    return _build_world_panel(parent, state, font, wrap)


def _build_world_panel(parent, state, font, wrap):
    frame = ttk.LabelFrame(parent, text="World")

    rows = [
        ("Date", state.date_str),
        ("Location", state.location),
    ]
    _fill_stat_rows(frame, rows, font, wrap)
    return frame


def _build_opponent_panel(parent, state, font, wrap):
    frame = ttk.LabelFrame(parent, text="Opponent")

    rows = [
        ("Name", state.interacting_with or "Unknown"),
        ("Health", f"{state.opponent_health} / {state.opponent_max_health}"),
    ]
    _fill_stat_rows(frame, rows, font, wrap)
    return frame


def _build_scene_panel(parent, state, image_size, font):
    frame = ttk.LabelFrame(parent, text="Scene")
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)

    subject = state.interacting_with or state.location
    canvas = tk.Canvas(
        frame, width=image_size, height=image_size, background="#3a3a3a", highlightthickness=0
    )
    canvas.create_text(
        image_size // 2,
        image_size // 2,
        text=f"[{subject}]",
        fill="white",
        width=image_size - 40,
        justify="center",
        font=font,
    )
    canvas.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
    return frame


def _open_main_menu(root, font):
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


def _build_result_box(parent, state, font):
    text = tk.Text(parent, height=3, wrap="word", state="disabled", font=font)
    _set_result_text(text, state.last_action_result)
    return text


def _set_result_text(text_widget, message):
    text_widget.configure(state="normal")
    text_widget.delete("1.0", "end")
    text_widget.insert("1.0", message)
    text_widget.configure(state="disabled")


def _build_bottom_section(parent, root, result_text, font, actions_height, menu_column_width):
    outer = ttk.Frame(parent)
    outer.columnconfigure(0, weight=1)
    outer.columnconfigure(1, minsize=menu_column_width)
    outer.rowconfigure(0, minsize=actions_height)

    _build_action_list(outer, result_text, font, actions_height).grid(
        row=0, column=0, sticky="nsew"
    )
    _build_menu_button(outer, root, font).grid(row=0, column=1, sticky="se", padx=(6, 0))

    return outer


def _build_menu_button(parent, root, font):
    frame = ttk.Frame(parent)
    ttk.Button(frame, text="Main Menu", command=lambda: _open_main_menu(root, font)).pack()
    return frame


def _build_action_list(parent, result_text, font, actions_height):
    outer = ttk.LabelFrame(parent, text="Actions")
    outer.rowconfigure(0, weight=1)
    outer.columnconfigure(0, weight=1)

    canvas = tk.Canvas(outer, height=actions_height, highlightthickness=0)
    scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)

    inner.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")

    for label, time_cost in DUMMY_ACTIONS:
        _add_action_button(inner, label, time_cost, result_text, font)

    return outer


def _add_action_button(parent, label, time_cost, result_text, font):
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
