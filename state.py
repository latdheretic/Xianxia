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


# --- cultivation ------------------------------------------------------------
#
# Four tracks advance in parallel. Each carries a progress number that starts
# at 0 and climbs; every whole 100 of it is one cultivation realm, and the
# realm is what the player sees on the main screen — the number itself is
# detail for the character sheet.
#
# Progress cannot cross a hundred on its own. It piles up against
# <realm ceiling> - 0.01, so a cultivator on the verge of their second realm
# sits visibly at 99.99 until a breakthrough carries them over.
PROGRESS_PER_REALM = 100
BOTTLENECK_MARGIN = 0.01  # also the display precision: two decimals
PROGRESS_DECIMALS = 2

# Recovery periods, in hours: how long the resource takes to refill from empty.
STAMINA_RECOVERY_HOURS = 2
QI_RECOVERY_HOURS = 7 * 24  # a week
# A night's sleep restores Shen; so does any action long enough to contain one.
SHEN_RECOVERY_HOURS = 24
# Qi cycling drives recovery far harder than idle time does.
QI_CYCLING_MULTIPLIER = 20


@dataclass(frozen=True)
class CultivationTrack:
    """Static description of one cultivation type.

    `resource_base` and `resource_per_progress` give the resource ceiling:
    max = base + per_progress * progress. Body tempering starts everyone
    with a usable body (base 100); the other three give nothing at all
    until their track is cultivated.
    """

    key: str
    name: str
    resource: str
    progress_attr: str
    resource_attr: str
    resource_base: float
    resource_per_progress: float
    realms: tuple

    def max_resource(self, progress: float) -> float:
        return self.resource_base + self.resource_per_progress * progress

    def realm_name(self, progress: float) -> str:
        realm = int(progress // PROGRESS_PER_REALM)
        if realm < len(self.realms):
            return self.realms[realm]
        # Past the charted ladder — name it rather than crash.
        return f"{self.realms[-1]} (Realm {realm + 1})"


BODY_REALMS = (
    "Mortal Frame",
    "Iron Skin",
    "Tempered Flesh",
    "Forged Bone",
    "Marrow Cleansing",
    "Organ Refinement",
    "Blood Transformation",
    "Adamant Body",
    "Indestructible Frame",
    "Immortal Physique",
)
QI_REALMS = (
    "Qi Sensing",
    "Qi Gathering",
    "Qi Condensation",
    "Foundation Establishment",
    "Core Formation",
    "Golden Core",
    "Meridian Ascension",
    "Void Refinement",
    "Heavenly Qi",
    "Qi Sovereign",
)
SPIRIT_REALMS = (
    "Clouded Mind",
    "Spirit Awakening",
    "Sea of Consciousness",
    "Divine Sense",
    "Spirit Manifestation",
    "Mind Palace",
    "Thousand Thoughts",
    "Spirit Sovereign",
    "Boundless Shen",
    "Celestial Mind",
)
SOUL_REALMS = (
    "Mortal Soul",
    "Karmic Awareness",
    "Severed Threads",
    "Karmic Weaving",
    "Fate Reading",
    "Destiny Binding",
    "Cycle Breaking",
    "Karmic Sovereign",
    "Fate Unwritten",
    "Eternal Soul",
)

TRACKS = (
    CultivationTrack(
        key="body",
        name="Body Tempering",
        resource="Stamina",
        progress_attr="body_progress",
        resource_attr="stamina",
        resource_base=100,
        resource_per_progress=1,
        realms=BODY_REALMS,
    ),
    CultivationTrack(
        key="qi",
        name="Qi Cultivation",
        resource="Qi",
        progress_attr="qi_progress",
        resource_attr="qi",
        resource_base=0,
        resource_per_progress=10,
        realms=QI_REALMS,
    ),
    CultivationTrack(
        key="spirit",
        name="Spirit Cultivation",
        resource="Shen",
        progress_attr="spirit_progress",
        resource_attr="shen",
        resource_base=0,
        resource_per_progress=5,
        realms=SPIRIT_REALMS,
    ),
    CultivationTrack(
        key="soul",
        name="Soul Cultivation",
        resource="Karma",
        progress_attr="soul_progress",
        resource_attr="karma",
        resource_base=0,
        resource_per_progress=100,
        realms=SOUL_REALMS,
    ),
)

TRACKS_BY_KEY = {track.key: track for track in TRACKS}


def format_progress(progress: float) -> str:
    return f"{progress:.{PROGRESS_DECIMALS}f}"


@dataclass
class GameState:
    name: str = "Wanderer"
    age: int = 16
    health: int = 100
    max_health: int = 100
    currency: int = 0

    # --- cultivation ---
    # Progress along each track; the realm names and resource ceilings are
    # derived from these, never stored alongside them.
    body_progress: float = 0.0
    qi_progress: float = 0.0
    spirit_progress: float = 0.0
    soul_progress: float = 0.0
    # Current pools. None means "start full", resolved in __post_init__ once
    # the ceilings are known — which for everything but stamina is zero
    # until that track has been cultivated at all.
    stamina: Optional[float] = None
    qi: Optional[float] = None
    shen: Optional[float] = None
    karma: Optional[float] = None

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
        for track in TRACKS:
            if getattr(self, track.resource_attr) is None:
                setattr(self, track.resource_attr, self.max_resource(track))

    @classmethod
    def new_game(cls) -> "GameState":
        return cls()

    # --- cultivation --------------------------------------------------------

    def progress(self, track: CultivationTrack) -> float:
        return getattr(self, track.progress_attr)

    def stage(self, track: CultivationTrack) -> str:
        """The written realm — what the main screen shows for this track."""
        return track.realm_name(self.progress(track))

    def max_resource(self, track: CultivationTrack) -> float:
        return track.max_resource(self.progress(track))

    def resource(self, track: CultivationTrack) -> float:
        return getattr(self, track.resource_attr)

    def bottleneck(self, track: CultivationTrack) -> float:
        """The most progress this track can reach without a breakthrough."""
        realm = int(self.progress(track) // PROGRESS_PER_REALM)
        return (realm + 1) * PROGRESS_PER_REALM - BOTTLENECK_MARGIN

    def at_bottleneck(self, track: CultivationTrack) -> bool:
        return self.progress(track) >= self.bottleneck(track)

    def add_progress(self, track: CultivationTrack, amount: float) -> float:
        """Advance a track, stopping dead at the realm bottleneck.

        Returns how much progress was actually gained, which is less than
        asked for when the cultivator runs into the ceiling.
        """
        if amount <= 0:
            return 0.0
        before = self.progress(track)
        after = min(round(before + amount, PROGRESS_DECIMALS), self.bottleneck(track))
        setattr(self, track.progress_attr, after)
        self._clamp_resource(track)
        return round(after - before, PROGRESS_DECIMALS)

    def breakthrough(self, track: CultivationTrack) -> bool:
        """Carry a bottlenecked track over into the next realm."""
        if not self.at_bottleneck(track):
            return False
        realm = int(self.progress(track) // PROGRESS_PER_REALM)
        setattr(self, track.progress_attr, float((realm + 1) * PROGRESS_PER_REALM))
        return True

    def _clamp_resource(self, track: CultivationTrack) -> None:
        """Keep a pool inside its ceiling; progress moves that ceiling."""
        capped = min(self.resource(track), self.max_resource(track))
        setattr(self, track.resource_attr, max(0.0, capped))

    def spend_resource(self, track: CultivationTrack, amount: float) -> float:
        """Draw on a pool, taking whatever is left if it is short."""
        spent = min(amount, self.resource(track))
        setattr(self, track.resource_attr, self.resource(track) - spent)
        return spent

    def restore_resource(self, track: CultivationTrack, amount: float) -> None:
        setattr(self, track.resource_attr, self.resource(track) + amount)
        self._clamp_resource(track)

    def recover_over(
        self, hours: float, *, qi_multiplier: float = 1, full_shen: bool = False
    ) -> None:
        """Refill pools for time passed. Karma is not among them.

        Each track refills at max/period per hour, so the rates track the
        ceilings as cultivation deepens: stamina is whole again in two
        hours, qi takes a week unless cycling drives it, and shen comes
        back with a night's sleep rather than trickling in.
        """
        if hours <= 0:
            return

        body, qi, spirit = (TRACKS_BY_KEY[key] for key in ("body", "qi", "spirit"))

        self.restore_resource(body, self.max_resource(body) * hours / STAMINA_RECOVERY_HOURS)
        self.restore_resource(
            qi, self.max_resource(qi) * hours * qi_multiplier / QI_RECOVERY_HOURS
        )
        if full_shen or hours >= SHEN_RECOVERY_HOURS:
            self.restore_resource(spirit, self.max_resource(spirit))
        # Karma has no natural recovery at all — only events return it.

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
