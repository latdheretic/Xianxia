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
extra width, same as before). A wider window — ultrawide and up —
caps the content at 16:9 and centers it, leaving blank window
background on the left/right rather than distorting anything.
Surplus *height*, by contrast, is not letterboxed: it is handed to
the action list, so a tall or square window simply shows more actions
before it needs to scroll. Scale is clamped to [MIN_SCALE, MAX_SCALE]
as the "minimum/maximum workable resolution"; root.minsize() keeps
the window from ever being shrunk past what MIN_SCALE needs.

Screens: the window hosts one screen at a time — SCREEN_MAIN (the
layout drawn above), SCREEN_CHARACTER (the full character sheet),
SCREEN_MENU (the main menu) and SCREEN_LOAD (the save picker). Every
screen swap happens in place; the app never opens a second window.
Clicking the player stats panel swaps to the character sheet, the
bottom-right Main Menu button swaps to the menu, and Back swaps
return. All screens are built at the same scale and placed in the
same box, so they follow identical dimension rules.

The game boots into SCREEN_MENU, which carries the game title above the
options: Continue Game (back to the run in progress), Load Game (pick
any run in the save directory), New Game and Exit. Continue Game is
disabled until a run has actually been started or loaded. There is no
Save command by design: runs persist automatically (see state.py), so
saving is never a thing the player has to remember to do.

Phase 1 (this file): static layout, dummy stats/state, inert action
buttons that print to console and echo a canned line into the result
box. Player stats panel is clickable and opens the character sheet.
Main Menu is just another bottom-row control (not a top corner button)
so it reads as one of the available choices, always anchored
bottom-right for consistency as the action list grows/shrinks.

Phase 2+: wire action buttons to actions.py, refresh stats panels and
scene image after each action resolves via a single refresh_ui(state)
entry point, and populate the action list from
get_available_actions(state) instead of DUMMY_ACTIONS.
"""

import tkinter as tk
from tkinter import ttk

from state import GameState, has_save_file, list_saves

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
BASE_HEADING_FONT_SIZE = 18
BASE_TITLE_FONT_SIZE = 34
BASE_SAVE_LIST_HEIGHT = 260
MIN_VALUE_WRAP = 60  # never wrap a stat value narrower than this
MENU_BUTTON_WIDTH = 22  # characters, so it tracks the scaled font
FONT_FAMILY = "TkDefaultFont"

RESIZE_DEBOUNCE_MS = 120

SCREEN_MAIN = "main"
SCREEN_CHARACTER = "character_sheet"
SCREEN_MENU = "main_menu"
SCREEN_LOAD = "load_game"

MENU_BUTTON_STYLE = "Menu.TButton"

GAME_TITLE = "Xianxia Cultivation Simulator"  # working title

DUMMY_ACTIONS = [
    ("Travel to the village", "2 days"),
    ("Rest", "8 hours"),
    ("Meditate at the spring", "1 month"),
    ("Harvest spirit herbs", "4 hours"),
    ("Spar with a fellow disciple", "1 hour"),
    ("Browse the market stalls", "instant"),
]


def build_ui(root, state):
    root.title(GAME_TITLE)
    root.configure(background=ttk.Style().lookup("TFrame", "background"))

    # Measured from the main screen even though the menu is shown first:
    # the game layout is what the window has to be big enough to hold.
    base_width, base_height = _measure_natural_size(root, state)
    root.minsize(round(base_width * MIN_SCALE), round(base_height * MIN_SCALE))

    # "state" lives here rather than in the enclosing argument because New
    # Game replaces the whole GameState; every rebuild reads the current one.
    # "run_active" is what Continue Game needs: at boot there is no run yet,
    # only the placeholder state the main screen is measured against.
    layout = {
        "content": None,
        "resize_job": None,
        "screen": SCREEN_MENU,
        "state": state,
        "run_active": False,
    }

    def apply_layout(window_w, window_h):
        scale, content_width = _compute_scale_and_width(
            window_w, window_h, base_width, base_height
        )
        # Surplus height goes to the content (and from there to the action
        # list) instead of becoming letterbox bars — a tall window should
        # show more actions, not padding. Width still letterboxes.
        content_height = max(round(base_height * scale), window_h)

        if layout["content"] is not None:
            layout["content"].destroy()
        content = _build_screen(
            root,
            layout["state"],
            scale,
            layout["screen"],
            show_screen,
            commands,
            layout["run_active"],
        )
        content.place(
            relx=0.5, rely=0.5, anchor="center", width=content_width, height=content_height
        )
        layout["content"] = content

    def show_screen(name):
        layout["screen"] = name
        apply_layout(root.winfo_width(), root.winfo_height())

    def start_new_game():
        # Phase 3: create this run's save file here too, so autosave has a
        # target from the very first action.
        layout["state"] = GameState.new_game()
        layout["run_active"] = True
        show_screen(SCREEN_MAIN)

    def load_game(slot):
        # Phase 3: layout["state"] = load_from_file(slot.path), set
        # run_active, then show_screen(SCREEN_MAIN).
        print(f"[stub] Load game — {slot.path} (loading lands in Phase 3)")

    commands = {
        "new_game": start_new_game,
        "load_game": load_game,
        "exit": root.destroy,
    }

    def on_resize_timeout():
        layout["resize_job"] = None
        if root.winfo_exists():
            apply_layout(root.winfo_width(), root.winfo_height())

    def cancel_pending_resize():
        if layout["resize_job"] is not None:
            root.after_cancel(layout["resize_job"])
            layout["resize_job"] = None

    def on_configure(event):
        if event.widget is not root:
            return
        cancel_pending_resize()
        layout["resize_job"] = root.after(RESIZE_DEBOUNCE_MS, on_resize_timeout)

    def on_destroy(event):
        # Otherwise a debounce still in flight fires against a dead window.
        if event.widget is root:
            cancel_pending_resize()

    root.bind("<Configure>", on_configure)
    root.bind("<Destroy>", on_destroy)
    root.geometry(f"{base_width}x{base_height}")
    apply_layout(base_width, base_height)


def _build_screen(root, state, scale, screen, show_screen, commands, run_active):
    """Screens share the window and the same scale/dimension rules."""
    if screen == SCREEN_CHARACTER:
        return _build_character_screen(root, state, scale, show_screen)
    if screen == SCREEN_MENU:
        return _build_menu_screen(root, scale, show_screen, commands, run_active)
    if screen == SCREEN_LOAD:
        return _build_load_screen(root, scale, show_screen, commands)
    return _build_content(root, state, scale, show_screen)


def _measure_natural_size(root, state):
    """Natural size = what the layout needs with every value on one line.

    The probe is measured with wrapping switched off. Left live, the
    dynamic wraplength binding would fire against the probe's pre-layout
    width, wrap the values to that, and the measurement would then report
    the narrow wrapped size — a base window too small to print its own
    stats unwrapped.
    """
    probe = _build_content(root, state, scale=1.0, show_screen=lambda name: None)
    for widget in _walk(probe):
        widget.unbind("<Configure>")
        if isinstance(widget, ttk.Label):
            widget.configure(wraplength=0)
    probe.update_idletasks()
    width, height = probe.winfo_reqwidth(), probe.winfo_reqheight()
    probe.destroy()
    return width, height


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


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


def _build_content(root, state, scale, show_screen):
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
    # Only the action row grows: extra window height becomes more visible
    # actions rather than empty space above/below the layout.
    content.rowconfigure(2, weight=1)

    _build_player_panel(content, state, font, show_screen).grid(
        row=0, column=0, sticky="nsew", padx=padding, pady=padding
    )
    _build_scene_panel(content, state, image_size, font).grid(
        row=0, column=1, sticky="nsew", padx=padding, pady=padding
    )
    _build_right_panel(content, state, font).grid(
        row=0, column=2, sticky="nsew", padx=padding, pady=padding
    )

    result_text = _build_result_box(content, state, font)
    result_text.grid(row=1, column=0, columnspan=3, sticky="ew", padx=padding, pady=(0, padding))

    _build_bottom_section(
        content, show_screen, result_text, font, actions_height, menu_column_width
    ).grid(row=2, column=0, columnspan=3, sticky="nsew", padx=padding, pady=(0, padding))

    return content


def _build_player_panel(parent, state, font, show_screen):
    frame = ttk.LabelFrame(parent, text="Player (click for details)")

    rows = [
        ("Name", state.name),
        ("Stage", state.stage),
        ("Health", f"{state.health} / {state.max_health}"),
        ("Qi", f"{state.qi} / {state.max_qi}"),
        ("Spirit Stones", str(state.currency)),
    ]
    _fill_stat_rows(frame, rows, font)

    _bind_click_recursive(frame, lambda event: show_screen(SCREEN_CHARACTER))
    return frame


def _fill_stat_rows(frame, rows, font, padx=4, pady=1):
    """Lay out "label: value" rows whose values wrap only when they must.

    wraplength has to track the value column's *rendered* width, not any
    design-time constant — the panels are elastic, so a fixed wraplength
    would keep breaking lines at the same word no matter how much room
    the panel actually has. So the labels start unwrapped (letting them
    report their true width to the geometry manager) and re-wrap from
    the real width on every <Configure>.
    """
    # Value column takes any slack so values sit against the keys.
    frame.columnconfigure(1, weight=1)

    value_labels = []
    for i, (label, value) in enumerate(rows):
        ttk.Label(frame, text=f"{label}:", font=font).grid(
            row=i, column=0, sticky="nw", padx=padx, pady=pady
        )
        value_label = ttk.Label(frame, text=value, font=font, justify="left")
        value_label.grid(row=i, column=1, sticky="w", padx=padx, pady=pady)
        value_labels.append(value_label)

    applied = {"wrap": None}

    def on_configure(event):
        # Measure against the panel's real width. The value column's own
        # allocated width can't be used: grid floors it at the unwrapped
        # label's request, so it never reports shrinking. The key column
        # is safe to read — key labels never wrap, so their width is
        # stable. bbox x doubles as the frame's border inset.
        key_cell = frame.grid_bbox(0, 0)
        if not key_cell:
            return
        inset, key_width = key_cell[0], key_cell[2]
        available = event.width - inset * 2 - key_width - padx * 2
        if available < MIN_VALUE_WRAP or available == applied["wrap"]:
            return
        applied["wrap"] = available
        for value_label in value_labels:
            value_label.configure(wraplength=available)

    frame.bind("<Configure>", on_configure)


def _bind_click_recursive(widget, callback):
    widget.bind("<Button-1>", callback)
    for child in widget.winfo_children():
        _bind_click_recursive(child, callback)


def _build_character_screen(root, state, scale, show_screen):
    """Full character sheet — an in-window screen, not a separate window.

    Built at the same scale and placed in the same box as the main screen,
    so it obeys the identical dimension rules.
    """
    font_size = max(6, round(BASE_FONT_SIZE * scale))
    font = (FONT_FAMILY, font_size)
    heading_font = (FONT_FAMILY, max(8, round(BASE_HEADING_FONT_SIZE * scale)), "bold")
    padding = max(2, round(BASE_PADDING * scale))

    content = ttk.Frame(root)
    content.columnconfigure(0, weight=1)
    content.rowconfigure(1, weight=1)

    ttk.Label(content, text="Character Sheet", font=heading_font).grid(
        row=0, column=0, sticky="w", padx=padding * 2, pady=(padding * 2, padding)
    )

    sheet = ttk.LabelFrame(content, text=state.name)
    sheet.grid(row=1, column=0, sticky="nsew", padx=padding, pady=(0, padding))

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
    _fill_stat_rows(sheet, rows, font, padx=padding * 2, pady=padding // 2 + 1)

    # Back sits bottom-right, same corner the main screen puts Main Menu in.
    footer = ttk.Frame(content)
    footer.grid(row=2, column=0, sticky="ew", padx=padding, pady=(0, padding))
    footer.columnconfigure(0, weight=1)
    ttk.Button(footer, text="Back", command=lambda: show_screen(SCREEN_MAIN)).grid(
        row=0, column=1, sticky="e"
    )

    return content


def _build_right_panel(parent, state, font):
    if state.in_combat:
        return _build_opponent_panel(parent, state, font)
    return _build_world_panel(parent, state, font)


def _build_world_panel(parent, state, font):
    frame = ttk.LabelFrame(parent, text="World")

    rows = [
        ("Date", state.date_str),
        ("Location", state.location),
    ]
    _fill_stat_rows(frame, rows, font)
    return frame


def _build_opponent_panel(parent, state, font):
    frame = ttk.LabelFrame(parent, text="Opponent")

    rows = [
        ("Name", state.interacting_with or "Unknown"),
        ("Health", f"{state.opponent_health} / {state.opponent_max_health}"),
    ]
    _fill_stat_rows(frame, rows, font)
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


def _menu_button_style(font):
    """ttk buttons take their font from a style, not a widget option."""
    ttk.Style().configure(MENU_BUTTON_STYLE, font=font)
    return MENU_BUTTON_STYLE


def _build_menu_screen(root, scale, show_screen, commands, run_active):
    """The main menu as an in-window screen — never a Toplevel popup.

    This is also the screen the game boots into, so it carries the game
    title above the options. No Save entry: runs autosave after every
    action (see state.py), so the menu is only ever about which run you
    are playing.
    """
    font = (FONT_FAMILY, max(6, round(BASE_FONT_SIZE * scale)))
    title_font = (FONT_FAMILY, max(10, round(BASE_TITLE_FONT_SIZE * scale)), "bold")
    padding = max(2, round(BASE_PADDING * scale))
    style = _menu_button_style(font)

    content = ttk.Frame(root)
    content.columnconfigure(0, weight=1)
    # Empty weighted rows above and below keep the menu vertically centred.
    content.rowconfigure(0, weight=1)
    content.rowconfigure(2, weight=1)

    box = ttk.Frame(content)
    box.grid(row=1, column=0)

    ttk.Label(box, text=GAME_TITLE, font=title_font, anchor="center").pack(
        pady=(0, padding * 6)
    )

    entries = [
        # Continue is dead at boot: nothing has been started or loaded yet.
        # Phase 3: also enable it when a save exists, and load the newest.
        ("Continue Game", lambda: show_screen(SCREEN_MAIN), run_active),
        ("Load Game", lambda: show_screen(SCREEN_LOAD), has_save_file()),
        ("New Game", commands["new_game"], True),
        ("Exit", commands["exit"], True),
    ]
    for label, command, enabled in entries:
        button = ttk.Button(
            box, text=label, command=command, style=style, width=MENU_BUTTON_WIDTH
        )
        if not enabled:
            button.state(["disabled"])
        button.pack(pady=padding)

    return content


def _build_load_screen(root, scale, show_screen, commands):
    """Save picker: lists the save directory, in-window like every screen."""
    font = (FONT_FAMILY, max(6, round(BASE_FONT_SIZE * scale)))
    heading_font = (FONT_FAMILY, max(8, round(BASE_HEADING_FONT_SIZE * scale)), "bold")
    padding = max(2, round(BASE_PADDING * scale))
    list_height = round(BASE_SAVE_LIST_HEIGHT * scale)
    style = _menu_button_style(font)

    slots = list_saves()

    content = ttk.Frame(root)
    content.columnconfigure(0, weight=1)
    content.rowconfigure(1, weight=1)

    ttk.Label(content, text="Load Game", font=heading_font).grid(
        row=0, column=0, sticky="w", padx=padding * 2, pady=(padding * 2, padding)
    )

    body = ttk.LabelFrame(content, text="Saved runs")
    body.grid(row=1, column=0, sticky="nsew", padx=padding, pady=(0, padding))
    body.columnconfigure(0, weight=1)
    body.rowconfigure(0, weight=1)

    save_list = None
    if slots:
        # tk.Listbox because ttk has no list widget; styled to match.
        save_list = tk.Listbox(
            body,
            font=font,
            height=max(3, list_height // max(1, font[1] * 2)),
            activestyle="none",
            highlightthickness=0,
            exportselection=False,
        )
        for slot in slots:
            save_list.insert("end", slot.label)
        save_list.selection_set(0)
        save_list.grid(row=0, column=0, sticky="nsew", padx=padding, pady=padding)

        scrollbar = ttk.Scrollbar(body, orient="vertical", command=save_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns", pady=padding)
        save_list.configure(yscrollcommand=scrollbar.set)
    else:
        ttk.Label(
            body,
            text="No saved runs yet — start a New Game.",
            font=font,
            anchor="center",
        ).grid(row=0, column=0, sticky="nsew", padx=padding * 2, pady=padding * 2)

    def load_selected():
        if save_list is None:
            return
        selection = save_list.curselection()
        if not selection:
            return
        commands["load_game"](slots[selection[0]])

    if save_list is not None:
        save_list.bind("<Double-Button-1>", lambda event: load_selected())

    # Back sits bottom-right, same corner as the other screens.
    footer = ttk.Frame(content)
    footer.grid(row=2, column=0, sticky="ew", padx=padding, pady=(0, padding))
    footer.columnconfigure(0, weight=1)

    load_button = ttk.Button(footer, text="Load", command=load_selected, style=style)
    if save_list is None:
        load_button.state(["disabled"])
    load_button.grid(row=0, column=1, sticky="e", padx=(0, padding))
    ttk.Button(
        footer, text="Back", command=lambda: show_screen(SCREEN_MENU), style=style
    ).grid(row=0, column=2, sticky="e")

    return content


def _build_result_box(parent, state, font):
    text = tk.Text(parent, height=3, wrap="word", state="disabled", font=font)
    _set_result_text(text, state.last_action_result)
    return text


def _set_result_text(text_widget, message):
    text_widget.configure(state="normal")
    text_widget.delete("1.0", "end")
    text_widget.insert("1.0", message)
    text_widget.configure(state="disabled")


def _build_bottom_section(
    parent, show_screen, result_text, font, actions_height, menu_column_width
):
    outer = ttk.Frame(parent)
    outer.columnconfigure(0, weight=1)
    outer.columnconfigure(1, minsize=menu_column_width)
    # minsize is the floor; weight lets the row take any surplus height.
    outer.rowconfigure(0, weight=1, minsize=actions_height)

    _build_action_list(outer, result_text, font, actions_height).grid(
        row=0, column=0, sticky="nsew"
    )
    _build_menu_button(outer, show_screen).grid(row=0, column=1, sticky="se", padx=(6, 0))

    return outer


def _build_menu_button(parent, show_screen):
    frame = ttk.Frame(parent)
    ttk.Button(
        frame, text="Main Menu", command=lambda: show_screen(SCREEN_MENU)
    ).pack()
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
