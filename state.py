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

Phase 4+: world/location data (visited/generated areas) gets added here
as it's produced by generation.py.
"""

from dataclasses import dataclass
from typing import Optional


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
    last_action_result: str = (
        "You awaken at the edge of the grove, unsure how you got here."
    )

    @classmethod
    def new_game(cls) -> "GameState":
        return cls()

    @property
    def date_str(self) -> str:
        return f"Day {self.day}, Month {self.month}, Year {self.year}"


# TODO (Phase 3): save_to_file(state, path) and load_from_file(path)
#   using json.dump / json.load. Keep save files human-readable
#   (indent=2) to make debugging easier during development.
