# Save file schema notes

Save files are JSON, one file per save slot, stored in this directory
(or an XDG-style user data dir — decide during Phase 3).

Keep the top level flat and include a `schema_version` integer from the
start, e.g.:

```json
{
  "schema_version": 1,
  "player": { "name": "...", "age": 16, "sect": null, "health": 162,
              "wallet": { "silver": 128, "spirit_stones": 3,
                          "contribution": 0 },
              "cultivation": { "body": 0.25, "qi": 0.4,
                               "spirit": 6.0, "soul": 0.0 },
              "pools": { "stamina": 100, "qi": 4, "shen": 30, "karma": 0 } },
  "world": { "seed": 12345,
             "current_date": {"year": 1004, "month": 1, "day": 1, "hour": 6},
             "journey_start": {"year": 1004, "month": 1, "day": 1},
             "visited_locations": {} },
  "flags": {}
}
```

`current_date` needs the hour as well as the date: the clock runs in whole
hours and actions are costed in them. `journey_start` is what the "day N,
year N of your cultivation journey" line counts from — it cannot be
derived from elapsed time, because day-costed actions reset the hour.
Months are 30 days and years are 12 months, so a date is only ever valid
with month 1-12 and day 1-30.

`cultivation` and `pools` are keyed by track, matching
`data/cultivation.json`. Save the progress integers and the current pools,
but never the realm names, the pool ceilings, max health or power level —
all are derived, and storing them would let a save contradict the data
file after it is tuned. Current health *is* saved: a wounded cultivator
should still be wounded when the run is loaded.

`wallet` is keyed like `CURRENCIES`. Save every balance, including
contribution points for a cultivator with no sect — leaving a sect should
not silently burn what was banked before, and whether the row is *shown*
is a UI question, not a storage one.
Pools are saved because they are spent and recovered independently of
progress. A save holding a track the data file no longer defines should be
ignored rather than fought over.

If the shape changes later, bump `schema_version` and write a small
migration function rather than breaking old saves outright.
