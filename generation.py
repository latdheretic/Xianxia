"""
generation.py

Procedural world/content generation. Not needed until Phase 4 —
leave empty (or with tiny placeholders) until Phases 1-3 are solid.

Planned responsibilities once we get here:
- Generate new locations/areas as the player explores.
- Generate location-specific flavor (and eventually the image reference
  to display for that scene).
- Seasonal effects: temperate locations should carry a line describing
  how the current season is treating them, shown in the location panel
  alongside the description. The calendar already gives us the season
  for free — months run Tiger through Ox with the year turning over on
  the first month of spring, so month 1-3 is spring, 4-6 summer, 7-9
  autumn, 10-12 winter. Not every location wants this: somewhere that
  is permanently frozen, volcanic, or otherwise outside the ordinary
  seasons should be able to opt out rather than print a nonsense line.
- Feed newly-discovered content into the action list (actions.py) so
  the bottom action bar reflects what's actually available at the
  player's current location.

Keep generation deterministic-from-seed if possible (store a world seed
in GameState) so saves stay reproducible/debuggable.
"""

# TODO (Phase 4): implement once Phases 1-3 are working end to end.
