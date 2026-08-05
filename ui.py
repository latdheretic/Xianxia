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

The menu is drawn on a background image (images/system/main_menu.png)
scaled to cover the whole window — it is the one screen that ignores
the letterbox and reaches the window edges. That screen is a Canvas
rather than a frame because Tk has no widget transparency: any ttk
container in front of the image would paint over it. Scaling needs
Pillow; without it the menu falls back to a flat colour and everything
else is unaffected.

Main Menu is just another bottom-row control (not a top corner button)
so it reads as one of the available choices, always anchored
bottom-right for consistency as the action list grows/shrinks.

Actions: the list comes from actions.get_available_actions(state), and a
click is handed straight back out to the dispatcher main.py supplied —
this module knows an action has a label and a time cost, and nothing
about what any of them do. Afterwards refresh_ui() rebuilds the current
screen, which is what makes the clock, stats and result line update
together; there is no per-widget update path to keep in sync.
"""

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from actions import get_available_actions
from state import (
    CURRENCIES,
    TRACKS,
    GameState,
    format_percent,
    format_progress,
    has_save_file,
    list_saves,
)

try:
    from PIL import Image, ImageOps, ImageTk

    PIL_AVAILABLE = True
except ImportError:  # the menu falls back to a flat colour without Pillow
    PIL_AVAILABLE = False

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
FONT_FAMILY = "TkDefaultFont"

# Menu buttons are laid out by hand on the background canvas (a ttk frame
# would paint an opaque slab over the image), so their box is in pixels.
BASE_MENU_BUTTON_WIDTH = 260
BASE_MENU_BUTTON_HEIGHT = 38
BASE_MENU_BUTTON_GAP = 10
BASE_MENU_TITLE_GAP = 44

IMAGE_DIR = Path(__file__).resolve().parent / "images"
SYSTEM_IMAGE_DIR = IMAGE_DIR / "system"
MENU_BACKGROUND_PATH = SYSTEM_IMAGE_DIR / "main_menu.png"

# Shown when the background image is unavailable. Light, because the title
# is black — a dark fallback would render it unreadable.
MENU_FALLBACK_BG = "#e9e3d5"
MENU_TITLE_FG = "#000000"
MENU_TITLE_HALO = "#f4efe2"  # paper tone, to lift the title off dark foliage

RESIZE_DEBOUNCE_MS = 120

SCREEN_MAIN = "main"
SCREEN_CHARACTER = "character_sheet"
SCREEN_MENU = "main_menu"
SCREEN_LOAD = "load_game"

MENU_BUTTON_STYLE = "Menu.TButton"

GAME_TITLE = "Xianxia Cultivation Simulator"  # working title

def build_ui(root, state, on_action=None):
    """Build the window.

    `on_action` is how a clicked action gets resolved: main.py passes the
    dispatcher, which is where autosave will hook in (Phase 3). It takes
    (state, action). Leaving it out makes actions inert, which is what the
    natural-size probe wants.
    """
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

        if layout["screen"] == SCREEN_MENU:
            # The menu has no fixed-ratio layout to protect, and its
            # background is meant to reach the window edges, so it takes
            # the whole window instead of the letterboxed content box.
            content_width, content_height = window_w, window_h

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
            (content_width, content_height),
            do_action,
        )
        content.place(
            relx=0.5, rely=0.5, anchor="center", width=content_width, height=content_height
        )
        layout["content"] = content

    def show_screen(name):
        layout["screen"] = name
        refresh_ui()

    def refresh_ui():
        """Redraw the current screen from the current state.

        The single entry point for "state changed, show it" — the layout
        is rebuilt from scratch each time anyway, so there is no separate
        set-this-label-to-that path to keep in sync.
        """
        apply_layout(root.winfo_width(), root.winfo_height())

    def do_action(action):
        """Hand a clicked action to main.py, then show the result."""
        if on_action is None:
            return
        on_action(layout["state"], action)
        refresh_ui()

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


def _build_screen(
    root, state, scale, screen, show_screen, commands, run_active, size, do_action
):
    """Screens share the window and the same scale/dimension rules."""
    if screen == SCREEN_CHARACTER:
        return _build_character_screen(root, state, scale, show_screen)
    if screen == SCREEN_MENU:
        return _build_menu_screen(root, scale, show_screen, commands, run_active, size)
    if screen == SCREEN_LOAD:
        return _build_load_screen(root, scale, show_screen, commands)
    return _build_content(root, state, scale, show_screen, do_action)


def _measure_natural_size(root, state):
    """Natural size = what the layout needs with every value on one line.

    The probe is measured with wrapping switched off. Left live, the
    dynamic wraplength binding would fire against the probe's pre-layout
    width, wrap the values to that, and the measurement would then report
    the narrow wrapped size — a base window too small to print its own
    stats unwrapped.

    Labels flagged keep_wraplength are the exception: those are sentences,
    not stat values, and measuring them on one line would size the window
    around a paragraph.
    """
    probe = _build_content(
        root, state, scale=1.0, show_screen=lambda name: None, do_action=lambda a: None
    )
    for widget in _walk(probe):
        widget.unbind("<Configure>")
        if isinstance(widget, ttk.Label) and not getattr(
            widget, "keep_wraplength", False
        ):
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


def _build_content(root, state, scale, show_screen, do_action):
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

    _build_player_panel(content, state, font, padding, show_screen).grid(
        row=0, column=0, sticky="nsew", padx=padding, pady=padding
    )
    _build_scene_panel(content, state, image_size, font).grid(
        row=0, column=1, sticky="nsew", padx=padding, pady=padding
    )
    _build_right_panel(content, state, font, side_panel_width, padding).grid(
        row=0, column=2, sticky="nsew", padx=padding, pady=padding
    )

    _build_result_box(content, state, font).grid(
        row=1, column=0, columnspan=3, sticky="ew", padx=padding, pady=(0, padding)
    )

    _build_bottom_section(
        content, show_screen, state, do_action, font, actions_height, menu_column_width
    ).grid(row=2, column=0, columnspan=3, sticky="nsew", padx=padding, pady=(0, padding))

    return content


def _format_pool(state, track):
    """A resource as "current / ceiling", both rounded to whole points."""
    return f"{state.resource(track):.0f} / {state.max_resource(track):.0f}"


def _cultivation_rows(state, with_progress):
    """Power level, then one row per track plus its resource.

    The main screen names the realm and nothing else; the character sheet
    is where the number behind it belongs — where in the realm's range the
    cultivator stands, and how far through it that is. 100.0% means the
    ceiling, and a breakthrough is the only way on.
    """
    # Health sits above power level because it follows from it, and power
    # level leads the tracks because it is their summary.
    rows = [
        ("Health", f"{state.health} / {state.max_health}"),
        ("Power Level", str(state.power_level)),
    ]
    for track in TRACKS:
        stage = state.stage(track)
        if with_progress:
            realm = state.realm(track)
            stage = (
                f"{stage}  ({format_progress(state.progress(track))} / "
                f"{realm.end} — {format_percent(state.realm_fraction(track))})"
            )
        rows.append((track.name, stage))
        rows.append((f"  {track.resource}", _format_pool(state, track)))
    return rows


def _currency_rows(state):
    """One row per currency, in the order they matter over a run."""
    rows = []
    for currency in CURRENCIES:
        # Sect money with no sect: the row stays, blank, rather than
        # showing a zero the player could never spend.
        value = str(state.balance(currency)) if state.has_currency(currency) else ""
        rows.append((currency.name, value))
    return rows


def _build_player_panel(parent, state, font, padding, show_screen):
    """The left column, in three blocks mirroring the right one.

    Who you are, what you have cultivated, what you can spend. Clicking
    anywhere in the column opens the full character sheet.
    """
    container = ttk.Frame(parent)
    container.columnconfigure(0, weight=1)
    # The cultivation block takes the slack, which leaves the purse sitting
    # at the bottom of the column where it belongs.
    container.rowconfigure(1, weight=1)

    identity = ttk.LabelFrame(container, text="Player (click for details)")
    rows = [("Name", state.name)]
    if state.sect:
        rows.append(("Sect", state.sect))
    _fill_stat_rows(identity, rows, font)
    identity.grid(row=0, column=0, sticky="new", pady=(0, padding))

    cultivation = ttk.LabelFrame(container, text="Cultivation")
    _fill_stat_rows(cultivation, _cultivation_rows(state, with_progress=False), font)
    cultivation.grid(row=1, column=0, sticky="nsew", pady=(0, padding))

    purse = ttk.LabelFrame(container, text="Currency")
    _fill_stat_rows(purse, _currency_rows(state), font)
    purse.grid(row=2, column=0, sticky="sew")

    _bind_click_recursive(container, lambda event: show_screen(SCREEN_CHARACTER))
    return container


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


def _fill_text_lines(frame, lines, font, wrap, padx=4, pady=1):
    """Stack sentence-style lines, wrapped to the panel rather than the window.

    Unlike the "label: value" rows, these are sentences: letting them ask
    for a single unwrapped line would drag the whole window's natural width
    out with them. So they carry a design wrap width (which the natural-size
    probe leaves alone, see _measure_natural_size) and still re-wrap to the
    panel's real width once there is one.
    """
    frame.columnconfigure(0, weight=1)

    labels = []
    for i, line in enumerate(lines):
        label = ttk.Label(
            frame, text=line, font=font, justify="left", wraplength=max(1, wrap)
        )
        label.keep_wraplength = True
        label.grid(row=i, column=0, sticky="w", padx=padx, pady=pady)
        labels.append(label)

    applied = {"wrap": wrap}

    def on_configure(event):
        cell = frame.grid_bbox(0, 0)
        if not cell:
            return
        available = event.width - cell[0] * 2 - padx * 2
        if available < MIN_VALUE_WRAP or available == applied["wrap"]:
            return
        applied["wrap"] = available
        for label in labels:
            label.configure(wraplength=available)

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

    rows = [("Name", state.name)]
    if state.sect:
        rows.append(("Sect", state.sect))
    rows.append(("Age", str(state.age)))
    # Here the realms come with the raw progress behind them, which is the
    # difference between this screen and the panel it opens from.
    rows += _cultivation_rows(state, with_progress=True)
    rows += _currency_rows(state)
    rows += [
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


def _build_right_panel(parent, state, font, panel_width, padding):
    """Time on top, always; below it whatever the player is engaged with.

    The context half switches on state.interacting_with: a person when the
    player is dealing with one, otherwise the place they are standing in.
    """
    container = ttk.Frame(parent)
    container.columnconfigure(0, weight=1)
    # Only the context half stretches; the time block wants its natural height.
    container.rowconfigure(1, weight=1)

    _build_time_panel(container, state, font, panel_width - padding * 4).grid(
        row=0, column=0, sticky="new", pady=(0, padding)
    )

    if state.interacting_with:
        context = _build_character_panel(container, state, font)
    else:
        context = _build_location_panel(container, state, font, panel_width - padding * 4)
    context.grid(row=1, column=0, sticky="nsew")

    return container


def _build_time_panel(parent, state, font, wrap):
    frame = ttk.LabelFrame(parent, text="Time")

    _fill_text_lines(frame, [state.time_str, state.journey_str], font, wrap)
    return frame


def _build_location_panel(parent, state, font, wrap):
    frame = ttk.LabelFrame(parent, text="Location")
    frame.columnconfigure(0, weight=1)

    # Two sub-frames because the helpers each own their parent's <Configure>
    # binding: the place is a stat value, the description is prose and has
    # to wrap rather than demand a window wide enough to hold one line.
    rows = ttk.Frame(frame)
    rows.grid(row=0, column=0, sticky="ew")
    _fill_stat_rows(rows, [("Place", state.location)], font)

    description = ttk.Frame(frame)
    description.grid(row=1, column=0, sticky="ew")
    # Phase 4: generation.py supplies this per location.
    _fill_text_lines(description, [state.location_detail], font, wrap)

    return frame


def _build_character_panel(parent, state, font):
    frame = ttk.LabelFrame(parent, text="Character")

    rows = [("Name", state.interacting_with)]
    if state.interacting_stage:
        rows.append(("Cultivation", state.interacting_stage))
    # Health is combat information; outside a fight it is not the player's
    # to know, so the row is simply absent.
    if state.in_combat:
        rows.append(
            ("Health", f"{state.interacting_health} / {state.interacting_max_health}")
        )
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


# Decoding the source on every resize would be wasteful, and dropping the
# PhotoImage on the floor would make Tk render nothing at all, so both the
# source image and the current scaled copy are held here.
_BACKGROUND_CACHE = {"path": None, "source": None, "size": None, "photo": None}
_WARNED = set()


def _warn_once(key, message):
    if key not in _WARNED:
        _WARNED.add(key)
        print(message)


def _menu_background(width, height):
    """The menu background, scaled to cover a width x height window.

    Cover, not stretch: the image is scaled until it fills the window and
    the overflow is cropped off centre. For a 16:9 source in anything
    narrower — down to the 4:3 the layout supports — that means it fits
    vertically and loses the sides, which is why the sides of the art are
    not meant to carry anything important. A window wider than the source
    fills edge to edge and trims a little off the top and bottom instead,
    rather than leaving bars.

    Returns None when there is nothing to draw; callers fall back to a
    flat colour.
    """
    if width <= 0 or height <= 0:
        return None
    if not PIL_AVAILABLE:
        _warn_once(
            "pillow",
            "[ui] Pillow is not installed — menu background disabled "
            "(pip install Pillow).",
        )
        return None
    if not MENU_BACKGROUND_PATH.is_file():
        _warn_once(
            "missing",
            f"[ui] No menu background at {MENU_BACKGROUND_PATH} — using a flat colour.",
        )
        return None

    cache = _BACKGROUND_CACHE
    if cache["path"] != MENU_BACKGROUND_PATH or cache["source"] is None:
        cache["source"] = Image.open(MENU_BACKGROUND_PATH).convert("RGB")
        cache["path"] = MENU_BACKGROUND_PATH
        cache["size"] = None

    if cache["size"] != (width, height):
        # ImageOps.fit is exactly cover + centre crop.
        fitted = ImageOps.fit(
            cache["source"], (width, height), method=Image.LANCZOS, centering=(0.5, 0.5)
        )
        cache["photo"] = ImageTk.PhotoImage(fitted)
        cache["size"] = (width, height)

    return cache["photo"]


def _build_menu_screen(root, scale, show_screen, commands, run_active, size):
    """The main menu as an in-window screen — never a Toplevel popup.

    This is also the screen the game boots into, so it carries the game
    title above the options. No Save entry: runs autosave after every
    action (see state.py), so the menu is only ever about which run you
    are playing.

    The screen *is* the background canvas. Tk has no widget transparency
    — any ttk frame in front of the image would paint an opaque slab over
    it — so the title is drawn as a canvas item and the buttons are
    positioned individually with create_window. That means laying the
    block out by hand, hence the pixel geometry below. `size` is the
    window size the caller is about to place this screen at; the canvas
    can't measure itself before it is mapped.
    """
    width, height = size
    font = (FONT_FAMILY, max(6, round(BASE_FONT_SIZE * scale)))
    title_size = max(10, round(BASE_TITLE_FONT_SIZE * scale))
    title_font = (FONT_FAMILY, title_size, "bold")
    style = _menu_button_style(font)

    button_width = round(BASE_MENU_BUTTON_WIDTH * scale)
    button_height = round(BASE_MENU_BUTTON_HEIGHT * scale)
    button_gap = round(BASE_MENU_BUTTON_GAP * scale)
    title_gap = round(BASE_MENU_TITLE_GAP * scale)
    title_height = round(title_size * 1.4)

    canvas = tk.Canvas(
        root,
        width=width,
        height=height,
        highlightthickness=0,
        borderwidth=0,
        background=MENU_FALLBACK_BG,
    )

    photo = _menu_background(width, height)
    if photo is not None:
        canvas.create_image(0, 0, anchor="nw", image=photo)
        # Tk keeps no reference of its own; without this the image is
        # garbage collected and the canvas draws blank.
        canvas.image = photo

    entries = [
        # Continue is dead at boot: nothing has been started or loaded yet.
        # Phase 3: also enable it when a save exists, and load the newest.
        ("Continue Game", lambda: show_screen(SCREEN_MAIN), run_active),
        ("Load Game", lambda: show_screen(SCREEN_LOAD), has_save_file()),
        ("New Game", commands["new_game"], True),
        ("Exit", commands["exit"], True),
    ]

    block_height = (
        title_height
        + title_gap
        + len(entries) * button_height
        + (len(entries) - 1) * button_gap
    )
    centre_x = width / 2
    top = (height - block_height) / 2

    # A light halo goes down first, then the black title over it. The art
    # is a pale ink wash, but the band the title crosses carries dark
    # foliage and ridgelines, so the text needs its own separation instead
    # of trusting the background to stay light. Four diagonal offsets
    # rather than one drop shadow, so it reads the same on every side.
    offset = max(1, round(2 * scale))
    title_y = top + title_height / 2
    for dx, dy in ((-offset, -offset), (offset, -offset), (-offset, offset), (offset, offset)):
        canvas.create_text(
            centre_x + dx,
            title_y + dy,
            text=GAME_TITLE,
            font=title_font,
            fill=MENU_TITLE_HALO,
        )
    canvas.create_text(
        centre_x, title_y, text=GAME_TITLE, font=title_font, fill=MENU_TITLE_FG
    )

    y = top + title_height + title_gap
    for label, command, enabled in entries:
        button = ttk.Button(canvas, text=label, command=command, style=style)
        if not enabled:
            button.state(["disabled"])
        canvas.create_window(
            centre_x, y, window=button, anchor="n", width=button_width, height=button_height
        )
        y += button_height + button_gap

    return canvas


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
    parent, show_screen, state, do_action, font, actions_height, menu_column_width
):
    outer = ttk.Frame(parent)
    outer.columnconfigure(0, weight=1)
    outer.columnconfigure(1, minsize=menu_column_width)
    # minsize is the floor; weight lets the row take any surplus height.
    outer.rowconfigure(0, weight=1, minsize=actions_height)

    _build_action_list(outer, state, do_action, font, actions_height).grid(
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


def _build_action_list(parent, state, do_action, font, actions_height):
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

    for action in get_available_actions(state):
        _add_action_button(inner, action, do_action)

    return outer


def _add_action_button(parent, action, do_action):
    button = ttk.Button(
        parent,
        text=f"{action.label}  —  {action.time_cost_label}",
        command=lambda: do_action(action),
    )
    button.pack(fill="x", padx=4, pady=2)
