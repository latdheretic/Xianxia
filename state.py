"""
state.py

Owns the GameState object: player stats, world state, and save/load logic.

Phase 1 (skeleton): just enough of a dataclass/dict to feed dummy stats
to the UI. No real save/load needed yet.

Phase 2: game clock (day/month/year) advances when actions resolve;
basic stats (qi, health, etc.) live here.

Phase 3: implement save_to_file() / load_from_file() using JSON. Keep
the schema flat and versioned (add a "schema_version" key) so future
changes to state shape can be migrated instead of breaking old saves.

Phase 4+: world/location data (visited/generated areas) gets added here
as it's produced by generation.py.
"""

# TODO (Phase 1): define a minimal GameState class/dataclass with
#   placeholder fields (name, qi, health, current_date, location)
#   and a classmethod for creating a fresh "new game" instance.

# TODO (Phase 3): save_to_file(state, path) and load_from_file(path)
#   using json.dump / json.load. Keep save files human-readable
#   (indent=2) to make debugging easier during development.
