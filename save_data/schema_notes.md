# Save file schema notes

Save files are JSON, one file per save slot, stored in this directory
(or an XDG-style user data dir — decide during Phase 3).

Keep the top level flat and include a `schema_version` integer from the
start, e.g.:

```json
{
  "schema_version": 1,
  "player": { "name": "...", "qi": 0, "health": 100, "stage": "..." },
  "world": { "seed": 12345, "current_date": {"year": 1, "month": 1, "day": 1},
             "visited_locations": {} },
  "flags": {}
}
```

If the shape changes later, bump `schema_version` and write a small
migration function rather than breaking old saves outright.
