# Save file schema notes

Save files are JSON, one file per save slot, stored in this directory
(or an XDG-style user data dir — decide during Phase 3).

Keep the top level flat and include a `schema_version` integer from the
start, e.g.:

```json
{
  "schema_version": 1,
  "player": { "name": "...", "age": 16, "health": 100, "currency": 0,
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

Save the cultivation progress numbers and the current pools, but never the
realm names or the pool ceilings — both are derived from progress, and
storing them would let a save contradict itself. Pools are saved because
they are spent and recovered independently of progress.

If the shape changes later, bump `schema_version` and write a small
migration function rather than breaking old saves outright.
