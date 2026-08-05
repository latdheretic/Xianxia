"""
actions.py

Defines the available player actions: their display label, time cost,
and resolution effect on GameState.

Every action is (label, time cost, effect), so that later (Phase 5) an
interruption check can be inserted into resolution without restructuring
this module: an interrupt is a check that runs between spending the time
and applying the effect, or partway through the time itself.

Time costs come in two shapes, matching state.py's two entry points:
hours (anything up to 48) resolve through advance_hours(), whole days (3
or more) through advance_days(), which also drops the character back to
the day start hour. An action costing less than an hour is free — the
clock has no finer grain than that. Action() enforces that split rather
than trusting each definition to remember it.

Phase 2 (this file): a small fixed list of test actions with real costs
and small stat effects, enough to prove the time-cost + resolution loop
before generation.py exists. Travel is the one state-dependent entry —
it offers whichever of the two placeholder locations you are not
standing in — which is the shape Phase 4 generalises.

Phase 4: the action list becomes dynamic, built from current
location/state data supplied by generation.py instead of hardcoded here.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from state import DAYS_PER_MONTH

# The costing convention from CLAUDE.md, enforced below.
MAX_ACTION_HOURS = 48
MIN_ACTION_DAYS = 3

# Phase 2 placeholder world: two locations to move between. Phase 4 hands
# this job to generation.py.
GROVE = "Whispering Bamboo Grove"
VILLAGE = "Riverbend Village"
LOCATION_DETAIL = {
    GROVE: "Bamboo in every direction, and a thin, clean qi.",
    VILLAGE: "Mud, millet and gossip. The qi here is trampled flat.",
}


def format_time_cost(hours: int, days: int) -> str:
    """How a cost is written on the button."""
    if days:
        if days % DAYS_PER_MONTH == 0:
            months = days // DAYS_PER_MONTH
            return f"{months} month" if months == 1 else f"{months} months"
        return f"{days} days"
    if hours <= 0:
        return "instant"
    return "1 hour" if hours == 1 else f"{hours} hours"


@dataclass(frozen=True)
class Action:
    """One thing the player can choose to do.

    An action costs either hours or days, never both — see the module
    docstring. `effect` takes the GameState and returns the line shown in
    the result box; leaving it out means the action only spends time.
    """

    label: str
    hours: int = 0
    days: int = 0
    effect: Optional[Callable] = field(default=None, repr=False)

    def __post_init__(self):
        if self.hours and self.days:
            raise ValueError(f"{self.label}: cost is hours or days, not both")
        if self.hours < 0 or self.days < 0:
            raise ValueError(f"{self.label}: time cost cannot be negative")
        if self.hours > MAX_ACTION_HOURS:
            raise ValueError(
                f"{self.label}: {self.hours}h exceeds {MAX_ACTION_HOURS}h — "
                "cost it in days instead"
            )
        if self.days and self.days < MIN_ACTION_DAYS:
            raise ValueError(
                f"{self.label}: {self.days} days is under {MIN_ACTION_DAYS} — "
                "cost it in hours instead"
            )

    @property
    def time_cost_label(self) -> str:
        return format_time_cost(self.hours, self.days)

    def spend_time(self, state) -> None:
        if self.days:
            state.advance_days(self.days)
        else:
            state.advance_hours(self.hours)

    def resolve(self, state) -> str:
        """Spend the time, apply the effect, and report what happened.

        Phase 5 inserts the interruption check here: between (or inside)
        spend_time and the effect, so a disturbed action can cost part of
        its time and resolve differently.
        """
        self.spend_time(state)
        if self.effect is None:
            message = f"You {self.label[0].lower()}{self.label[1:]}."
        else:
            message = self.effect(state)
        state.last_action_result = message
        return message


# --- effects ----------------------------------------------------------------
#
# Each takes the GameState, changes it, and returns the line for the result
# box. Deliberately small: these exist to prove the loop, not to be balanced.


def _travel_to(destination):
    def effect(state):
        state.location = destination
        state.location_detail = LOCATION_DETAIL[destination]
        return f"You walk the road to {destination}, arriving footsore but whole."

    return effect


def _rest(state):
    healed = min(15, state.max_health - state.health)
    state.health += healed
    if healed:
        return f"You sleep the night through and recover {healed} health."
    return "You sleep the night through. There was nothing left to mend."


def _meditate(state):
    gained = min(20, state.max_qi - state.qi)
    state.qi += gained
    if gained:
        return (
            "You sit with the spring until the month turns, and draw "
            f"{gained} qi into your dantian."
        )
    return "You sit with the spring until the month turns. Your dantian is already full."


def _harvest(state):
    state.currency += 2
    return "You cut what the ridge will spare. The herbs fetch 2 spirit stones."


def _spar(state):
    lost = min(5, state.health)
    state.health -= lost
    return f"You trade blows until your guard fails. {lost} health, and a lesson."


def _browse(state):
    return "You drift past the stalls. Nothing here is worth a cultivator's time."


def get_available_actions(state):
    """The actions offered for the current state.

    Phase 4 replaces the fixed spine of this list with generated content;
    the travel entry already shows the pattern of asking the state what
    makes sense right now.
    """
    destination = VILLAGE if state.location == GROVE else GROVE

    return [
        Action(f"Travel to {destination}", hours=48, effect=_travel_to(destination)),
        Action("Rest", hours=8, effect=_rest),
        Action("Meditate at the spring", days=DAYS_PER_MONTH, effect=_meditate),
        Action("Harvest spirit herbs", hours=4, effect=_harvest),
        Action("Spar with a fellow disciple", hours=1, effect=_spar),
        Action("Browse the market stalls", effect=_browse),
    ]
