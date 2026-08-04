"""
state.py

Owns the GameState object: player stats, world state, and save/load logic.

Phase 1 (skeleton): minimal dataclass with placeholder fields, enough to
feed dummy stats to the UI. No real save/load yet.

Phase 2: game clock (day/month/year) advances when actions resolve;
basic stats (qi, health, etc.) get real resolution logic here.

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
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Phase 1 placeholder location. Phase 3 decides for real between this and
# an XDG-style ~/.local/share/<gamename>/ (see save_data/schema_notes.md).
SAVE_DIR = Path(__file__).resolve().parent / "save_data"
SAVE_SUFFIX = ".json"


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
    day: int = 1
    month: int = 1
    year: int = 1
    location: str = "Whispering Bamboo Grove"
    interacting_with: Optional[str] = None
    in_combat: bool = False
    opponent_health: int = 0
    opponent_max_health: int = 0
    last_action_result: str = (
        "You awaken at the edge of the grove, unsure how you got here."
    )
    # Which file this run autosaves into. Set when the run is created;
    # None only for Phase 1 states that were never persisted.
    save_path: Optional[Path] = None

    @classmethod
    def new_game(cls) -> "GameState":
        return cls()

    @property
    def date_str(self) -> str:
        return f"Day {self.day}, Month {self.month}, Year {self.year}"


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
