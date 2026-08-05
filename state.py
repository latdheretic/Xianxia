"""
state.py

Owns the GameState object: player stats, world state, and save/load logic.

Phase 1 (skeleton): minimal dataclass with placeholder fields, enough to
feed dummy stats to the UI. No real save/load yet.

Phase 2: the clock and calendar live here — twelve 30-day months named
for the zodiac, a 24-hour day in whole hours, and the two ways time can
be spent (advance_hours / advance_days). Stats get their real resolution
logic here as the rest of Phase 2 lands.

Phase 3: implement save_to_file() / load_from_file() using JSON. Keep
the schema flat and versioned (add a "schema_version" key) so future
changes to state shape can be migrated instead of breaking old saves.

Saving is automatic (roguelike-style persistent state): the game writes
back to the run's own save file after every resolved action, so there is
no manual "Save" command in the UI. A save file *is* the run — if a risk
goes badly, that is the state you are left with.

Phase 4+: world/location data (visited/generated areas) gets added here
as it's produced by generation.py.
"""

import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Phase 1 placeholder location. Phase 3 decides for real between this and
# an XDG-style ~/.local/share/<gamename>/ (see save_data/schema_notes.md).
SAVE_DIR = Path(__file__).resolve().parent / "save_data"
SAVE_SUFFIX = ".json"

# --- calendar ---------------------------------------------------------------
#
# A simplified, thematic calendar: twelve 30-day months, each named for a
# zodiac animal, so every year is exactly 360 days. The year turns over on
# the first month of spring — the month of the Tiger — which is why the
# month list starts there rather than at the Rat.
MONTHS = (
    "Tiger",
    "Rabbit",
    "Dragon",
    "Snake",
    "Horse",
    "Sheep",
    "Monkey",
    "Rooster",
    "Dog",
    "Pig",
    "Rat",
    "Ox",
)
# Years are numbered by the Imperial Era only — no zodiac animal. Naming
# both the month and the year made the time panel read as clutter.
DAYS_PER_MONTH = 30
MONTHS_PER_YEAR = 12
DAYS_PER_YEAR = DAYS_PER_MONTH * MONTHS_PER_YEAR
HOURS_PER_DAY = 24

# A run begins at dawn, and any action measured in days rather than hours
# leaves the character picking up again at the same hour.
DAY_START_HOUR = 6

# The era is already ancient when the player's story starts; how ancient is
# rolled per run.
MIN_START_YEAR = 500
MAX_START_YEAR = 1500


def absolute_day(year: int, month: int, day: int) -> int:
    """Days since the start of era year 1, as a single number.

    Doing the arithmetic through this and back again keeps month/year
    rollover in one place instead of scattering carry logic.
    """
    return (year - 1) * DAYS_PER_YEAR + (month - 1) * DAYS_PER_MONTH + (day - 1)


def from_absolute_day(absolute: int):
    """Inverse of absolute_day(): returns (year, month, day)."""
    year, remainder = divmod(absolute, DAYS_PER_YEAR)
    month, day = divmod(remainder, DAYS_PER_MONTH)
    return year + 1, month + 1, day + 1


def month_animal(month: int) -> str:
    """The zodiac animal naming a given month."""
    return MONTHS[(month - 1) % MONTHS_PER_YEAR]


def random_start_year() -> int:
    return random.randint(MIN_START_YEAR, MAX_START_YEAR)


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


@dataclass
class GameState:
    name: str = "Wanderer"
    stage: str = "Body Tempering — 1st Layer"
    age: int = 16
    health: int = 100
    max_health: int = 100
    qi: int = 10
    max_qi: int = 100
    currency: int = 0

    # --- clock and calendar ---
    hour: int = DAY_START_HOUR
    day: int = 1
    month: int = 1
    year: int = field(default_factory=random_start_year)
    # Where the cultivation journey began, so its day/year count survives
    # the hour resets that long actions cause. Filled in from the current
    # date when a run is created.
    start_year: Optional[int] = None
    start_month: int = 1
    start_day: int = 1

    # --- what the player is looking at ---
    location: str = "Whispering Bamboo Grove"
    location_detail: str = "Bamboo in every direction, and a thin, clean qi."
    # None means the player is engaged with the place rather than a person;
    # the right-hand panel switches on exactly this.
    interacting_with: Optional[str] = None
    interacting_stage: Optional[str] = None
    in_combat: bool = False
    interacting_health: int = 0
    interacting_max_health: int = 0

    last_action_result: str = (
        "You awaken at the edge of the grove, unsure how you got here."
    )
    # Which file this run autosaves into. Set when the run is created;
    # None only for Phase 1 states that were never persisted.
    save_path: Optional[Path] = None

    def __post_init__(self):
        if self.start_year is None:
            self.start_year = self.year
            self.start_month = self.month
            self.start_day = self.day

    @classmethod
    def new_game(cls) -> "GameState":
        return cls()

    # --- advancing time -----------------------------------------------------
    #
    # Two entry points because actions come in two shapes: short ones costed
    # in hours (up to two days' worth), and long ones costed in whole days.
    # Anything under an hour is free — the clock has no finer grain.

    def advance_hours(self, hours: int) -> None:
        """Advance by whole hours, rolling the date over as needed."""
        if hours <= 0:
            return
        total = self.hour + hours
        self._add_days(total // HOURS_PER_DAY)
        self.hour = total % HOURS_PER_DAY

    def advance_days(self, days: int) -> None:
        """Advance whole days, leaving the character starting again at dawn."""
        if days <= 0:
            return
        self._add_days(days)
        self.hour = DAY_START_HOUR

    def _add_days(self, days: int) -> None:
        if days <= 0:
            return
        self.year, self.month, self.day = from_absolute_day(
            absolute_day(self.year, self.month, self.day) + days
        )

    # --- how time reads -----------------------------------------------------

    @property
    def elapsed_days(self) -> int:
        """Whole days since the journey began."""
        return absolute_day(self.year, self.month, self.day) - absolute_day(
            self.start_year, self.start_month, self.start_day
        )

    @property
    def journey_years(self) -> int:
        """Whole years of cultivation completed."""
        return self.elapsed_days // DAYS_PER_YEAR

    @property
    def journey_days(self) -> int:
        """Days of cultivation on top of those whole years."""
        return self.elapsed_days % DAYS_PER_YEAR

    @property
    def clock_str(self) -> str:
        """Whole hours on a 12-hour clock: midnight is 12:00 AM, noon 12:00 PM."""
        suffix = "AM" if self.hour < 12 else "PM"
        hour = self.hour % 12 or 12
        return f"{hour}:00 {suffix}"

    @property
    def time_str(self) -> str:
        """The one line the time panel leads with."""
        return f"{self.clock_str} Day {self.day} in the month of the {month_animal(self.month)}"

    @property
    def date_str(self) -> str:
        """Longer form, for the character sheet — this one carries the year."""
        return (
            f"Day {self.day} in the month of the {month_animal(self.month)}, "
            f"Imperial Era {self.year}"
        )

    @property
    def journey_str(self) -> str:
        # Either half drops out at zero rather than reading "0 years" or
        # "0 days and 2 years". The one exception is the first day of a
        # run, where dropping both would leave the sentence with nothing
        # to say.
        parts = []
        if self.journey_days or not self.journey_years:
            parts.append(_plural(self.journey_days, "day"))
        if self.journey_years:
            parts.append(_plural(self.journey_years, "year"))
        return "You have been cultivating for " + " and ".join(parts) + "."


@dataclass
class SaveSlot:
    """One save file on disk, as listed on the Load Game screen."""

    path: Path
    label: str
    modified: float


# TODO (Phase 3): save_to_file(state, path) and load_from_file(path)
#   using json.dump / json.load. Keep save files human-readable
#   (indent=2) to make debugging easier during development.
#   autosave(state) writes to state.save_path and is called after every
#   action resolves — never from the UI directly.


def list_saves():
    """Every save file in SAVE_DIR, newest first.

    Phase 1: the directory holds no saves yet, so this returns an empty
    list and the Load Game screen shows its empty state. Once Phase 3
    writes files, the labels here should come from the save contents
    (name / stage / date) rather than the bare filename.
    """
    if not SAVE_DIR.is_dir():
        return []

    slots = []
    for path in SAVE_DIR.glob("*" + SAVE_SUFFIX):
        if path.is_file():
            slots.append(
                SaveSlot(path=path, label=path.stem, modified=path.stat().st_mtime)
            )

    slots.sort(key=lambda slot: slot.modified, reverse=True)
    return slots


def has_save_file() -> bool:
    """Whether any run exists to load."""
    return bool(list_saves())


def ensure_save_dir() -> None:
    """Create SAVE_DIR if missing, so the first autosave has somewhere to go."""
    os.makedirs(SAVE_DIR, exist_ok=True)
