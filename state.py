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

import json
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

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
# Four tracks advance in parallel. Each carries an integer progress value
# that starts at 0 and climbs; the realm it falls into is what the player
# sees on the main screen.
#
# None of it is hardcoded here. The realm ladders, their ranges, the
# resource ceilings and the recovery rules all live in data/cultivation.json
# so the numbers can be tuned without touching code. This module only knows
# how to read that file and apply it.
#
# Progress cannot leave its realm on its own: it piles up against the top of
# the current range, and only a breakthrough carries a cultivator into the
# next one.
CULTIVATION_DATA_PATH = Path(__file__).resolve().parent / "data" / "cultivation.json"

RECOVERY_RATE = "rate"  # refills at max/hours per hour
RECOVERY_FULL = "full"  # refills entirely, once enough hours pass at once
RECOVERY_NONE = "none"  # never refills with time; events only
RECOVERY_MODES = (RECOVERY_RATE, RECOVERY_FULL, RECOVERY_NONE)


@dataclass(frozen=True)
class Realm:
    """One rung of a track's ladder, and the progress range that reaches it."""

    name: str
    start: int
    end: int

    @property
    def span(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class CultivationTrack:
    """Static description of one cultivation type, read from the data file.

    `resource_base` and `resource_per_progress` give the resource ceiling:
    max = base + per_progress * progress. Body tempering starts everyone
    with a usable body (base 100); the other three give nothing at all
    until their track is cultivated.
    """

    key: str
    name: str
    resource: str
    resource_base: float
    resource_per_progress: float
    recovery_mode: str
    recovery_hours: float
    realms: tuple

    def max_resource(self, progress: int) -> float:
        return self.resource_base + self.resource_per_progress * progress

    def realm_for(self, progress: int) -> Realm:
        """The realm a progress value falls in, clamped to the ladder's ends."""
        for realm in self.realms:
            if progress <= realm.end:
                return realm
        return self.realms[-1]

    def next_realm(self, realm: Realm):
        index = self.realms.index(realm) + 1
        return self.realms[index] if index < len(self.realms) else None


@dataclass(frozen=True)
class CultivationData:
    """Everything data/cultivation.json supplies, in one piece."""

    tracks: tuple
    qi_cycling_multiplier: float
    base_health: float


def _load_cultivation(path=CULTIVATION_DATA_PATH):
    """Read data/cultivation.json into tracks, validating as we go.

    The file is required: a silent fallback to built-in defaults would
    defeat the point of having it, and would hide a typo in the data
    behind values nobody edited.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Cultivation data file missing: {path}. It defines the realm "
            "ladders and resource rules the game cannot run without."
        ) from None
    except json.JSONDecodeError as error:
        raise ValueError(f"{path} is not valid JSON: {error}") from None

    tracks = []
    for key, entry in data["tracks"].items():
        realms = []
        previous = None
        for raw in entry["realms"]:
            realm = Realm(name=raw["name"], start=int(raw["start"]), end=int(raw["end"]))
            if realm.end <= realm.start:
                raise ValueError(f"{path}: realm {realm.name!r} ends before it starts")
            if previous is None:
                if realm.start != 0:
                    raise ValueError(f"{path}: track {key!r} must start at 0")
            elif realm.start != previous.end + 1:
                # A gap would leave progress values with no realm at all.
                raise ValueError(
                    f"{path}: track {key!r} jumps from {previous.end} to "
                    f"{realm.start} — realm ranges must be contiguous"
                )
            realms.append(realm)
            previous = realm

        if not realms:
            raise ValueError(f"{path}: track {key!r} has no realms")

        recovery = entry.get("recovery", {"mode": RECOVERY_NONE})
        mode = recovery.get("mode", RECOVERY_NONE)
        if mode not in RECOVERY_MODES:
            raise ValueError(
                f"{path}: track {key!r} has unknown recovery mode {mode!r}; "
                f"expected one of {', '.join(RECOVERY_MODES)}"
            )

        tracks.append(
            CultivationTrack(
                key=key,
                name=entry["name"],
                resource=entry["resource"],
                resource_base=float(entry["resource_base"]),
                resource_per_progress=float(entry["resource_per_progress"]),
                recovery_mode=mode,
                recovery_hours=float(recovery.get("hours", 0)),
                realms=tuple(realms),
            )
        )

    base_health = float(data.get("base_health", 100))
    if base_health < 0:
        raise ValueError(f"{path}: base_health cannot be negative")

    return CultivationData(
        tracks=tuple(tracks),
        qi_cycling_multiplier=float(data.get("qi_cycling_multiplier", 1)),
        base_health=base_health,
    )


_DATA = _load_cultivation()
TRACKS = _DATA.tracks
QI_CYCLING_MULTIPLIER = _DATA.qi_cycling_multiplier
# What a cultivator would have with no cultivation at all; power level is
# added on top. Perks and gear will modify it once they exist.
BASE_HEALTH = _DATA.base_health
TRACKS_BY_KEY = {track.key: track for track in TRACKS}


def format_progress(progress: int) -> str:
    return str(int(progress))


def format_percent(fraction: float) -> str:
    """Progress through a realm, to a tenth — one point of a 1000 span."""
    return f"{fraction * 100:.1f}%"


@dataclass
class GameState:
    name: str = "Wanderer"
    age: int = 16
    # Current health only. The ceiling is derived — see max_health — so a
    # cultivator who deepens a track gets tougher without anything here
    # having to be updated. None means "start whole".
    health: Optional[int] = None
    currency: int = 0

    # --- cultivation ---
    # Keyed by track, matching data/cultivation.json. Only these two move:
    # realm names and pool ceilings are always derived, never stored, and a
    # new track in the data file needs no new field here.
    cultivation: Dict[str, int] = field(default_factory=dict)
    pools: Dict[str, float] = field(default_factory=dict)

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
        # Anything the caller left out starts at zero progress with a full
        # pool — which for every track but the body is a pool of nothing.
        for track in TRACKS:
            self.cultivation.setdefault(track.key, 0)
        for track in TRACKS:
            self.pools.setdefault(track.key, self.max_resource(track))
        # Health last: its ceiling depends on the cultivation above.
        if self.health is None:
            self.health = self.max_health

    @classmethod
    def new_game(cls) -> "GameState":
        return cls()

    # --- cultivation --------------------------------------------------------

    def progress(self, track: CultivationTrack) -> int:
        return self.cultivation[track.key]

    def realm(self, track: CultivationTrack) -> Realm:
        return track.realm_for(self.progress(track))

    def stage(self, track: CultivationTrack) -> str:
        """The written realm — what the main screen shows for this track."""
        return self.realm(track).name

    def realm_fraction(self, track: CultivationTrack) -> float:
        """How far through the current realm, 0.0 to 1.0.

        1.0 means the cultivator is against the ceiling of the realm and
        needs a breakthrough — the character sheet shows this as 100.0%.
        """
        realm = self.realm(track)
        if realm.span <= 0:
            return 1.0
        return (self.progress(track) - realm.start) / realm.span

    def max_resource(self, track: CultivationTrack) -> float:
        return track.max_resource(self.progress(track))

    def resource(self, track: CultivationTrack) -> float:
        return self.pools[track.key]

    @property
    def max_health(self) -> int:
        """Baseline plus power level.

        Derived rather than stored, so cultivating makes a character
        tougher on its own. Perks and gear will modify this too once
        generation exists; they belong here, not in a saved number.
        """
        return int(BASE_HEALTH) + self.power_level

    @property
    def power_level(self) -> int:
        """One number for what a cultivator can handle.

        The strongest track carries it, plus the average of the others —
        so a lopsided cultivator still counts for something, but breadth
        is worth less than depth. Later this drives technique strength,
        and hostile locations advertise their own so the player can judge
        whether they are out of their depth.
        """
        values = sorted((self.progress(track) for track in TRACKS), reverse=True)
        if not values:
            return 0
        highest, rest = values[0], values[1:]
        average = sum(rest) / len(rest) if rest else 0
        # Half-up: Python's round() would send 2.5 to 2, which reads as a
        # bug in a stat the player is comparing against a threat's number.
        return int(highest + average + 0.5)

    def bottleneck(self, track: CultivationTrack) -> int:
        """The most progress this track can reach without a breakthrough."""
        return self.realm(track).end

    def at_bottleneck(self, track: CultivationTrack) -> bool:
        return self.progress(track) >= self.bottleneck(track)

    def add_progress(self, track: CultivationTrack, amount: int) -> int:
        """Advance a track, stopping dead at the top of its realm.

        Returns how much progress was actually gained, which is less than
        asked for when the cultivator runs into the ceiling.
        """
        amount = int(amount)
        if amount <= 0:
            return 0
        before = self.progress(track)
        after = min(before + amount, self.bottleneck(track))
        self.cultivation[track.key] = after
        self._clamp_resource(track)
        return after - before

    def breakthrough(self, track: CultivationTrack) -> bool:
        """Carry a bottlenecked track over into the next realm.

        Fails at the top of the ladder: there is nowhere to go until the
        data file defines another realm.
        """
        if not self.at_bottleneck(track):
            return False
        following = track.next_realm(self.realm(track))
        if following is None:
            return False
        self.cultivation[track.key] = following.start
        return True

    def _clamp_resource(self, track: CultivationTrack) -> None:
        """Keep a pool inside its ceiling; progress moves that ceiling."""
        capped = min(self.resource(track), self.max_resource(track))
        self.pools[track.key] = max(0.0, capped)

    def spend_resource(self, track: CultivationTrack, amount: float) -> float:
        """Draw on a pool, taking whatever is left if it is short."""
        spent = min(amount, self.resource(track))
        self.pools[track.key] = self.resource(track) - spent
        return spent

    def restore_resource(self, track: CultivationTrack, amount: float) -> None:
        self.pools[track.key] = self.resource(track) + amount
        self._clamp_resource(track)

    def recover_over(
        self, hours: float, *, qi_multiplier: float = 1, slept: bool = False
    ) -> None:
        """Refill pools for time passed, following each track's own rule.

        A "rate" track refills at max/hours per hour, so its speed tracks
        the ceiling as cultivation deepens. A "full" track comes back all
        at once, but only when the time contains a proper rest. A "none"
        track — karma — never returns with time at all; events are its
        only source.
        """
        if hours <= 0:
            return

        for track in TRACKS:
            if track.recovery_mode == RECOVERY_RATE:
                multiplier = qi_multiplier if track.key == "qi" else 1
                gain = self.max_resource(track) * hours * multiplier
                self.restore_resource(track, gain / track.recovery_hours)
            elif track.recovery_mode == RECOVERY_FULL:
                if slept or hours >= track.recovery_hours:
                    self.restore_resource(track, self.max_resource(track))

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
