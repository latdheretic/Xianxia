"""
actions.py

Defines the available player actions: their display label, time cost,
and resolution effect on GameState.

Design goal: model every action as (label, time_cost, resolve_fn) so
that later (Phase 5) an interruption check can be inserted into
resolution without restructuring this module.

Phase 2: hardcode a small fixed list of test actions, e.g.
    - "View stats"        -> 0 time cost, no state change (just refresh UI)
    - "Meditate"           -> 1 month, +qi
    - "Rest"                -> 1 day, +health
This proves the time-cost + resolution loop before generation.py exists.

Phase 4: action list becomes dynamic, built from current location/state
data supplied by generation.py instead of being fully hardcoded.
"""

# TODO (Phase 2): define a simple Action representation (namedtuple/
#   dataclass) with fields: label, time_cost, resolve(state) -> None
#   and a get_available_actions(state) -> list[Action] function.
