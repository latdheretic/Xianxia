# Save file schema notes

Save files are JSON, one file per save slot, stored in this directory
(or an XDG-style user data dir — decide during Phase 3).

Keep the top level flat and include a `schema_version` integer from the
start, e.g.:

```json
{
  "schema_version": 1,
  "player": { "name": "...", "qi": 0, "health": 100, "stage": "..." },
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

If the shape changes later, bump `schema_version` and write a small
migration function rather than breaking old saves outright.
