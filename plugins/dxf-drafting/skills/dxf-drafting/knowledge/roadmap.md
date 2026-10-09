# Roadmap: capabilities not built yet (highest value first). Remove when done (note in CHANGELOG); add gaps you spot.

0. **Ground floor follow-ups**: draw the ~34 beams/walls listed for review (walls 20/xx need an outline detector on the wall layers and the user's rule for non-shaft walls; beams with a single edge line); verify the 30-wide BEARING case; the old example sheet still carries the user's old 1-1..5-5 under the same numbers.
1. **Close the loop plan -> section**: `plan_cuts.py` gives beam/slab labels and view directions; still missing: deciding slab SIDES from the plan geometry (slab panels / openings next to the beam) and a one-command batch (`--all`: read cuts, pick free cells, draw + restyle every section, one render sheet).
2. **Section 5-5** (25-wide wall at the stair core): no example mapped, no cell; ask the user for the template.
3. **Bar counts**: copied from max spacings fitted to the examples (UNVERIFIED); verify with the user on the first approved set and store per-beam counts in the profile.
4. **More shapes** from the ground-floor sheet: 2-level slab (example 3-3), panel with cores (example 5-5), the second detail (60 x 14 horizontal bar).
5. **Other drawing types** (`פרטים וחתכים אוטומטים.dxf`, `שכבות.dxf`, plans: grids, labels, chains), layer compliance vs `anthropic-skills:construction-layers`, quantities (areas, rebar lengths from the `L=` notes -> CSV/XLSX), drawing QA (duplicates texts, overlaps, stale overrides).
6. **Second office / drawing style**: copy `profiles/israeli-structural.json`, change values, add a test case; keep recipes free of constants (legacy rebar recipes still violate this).
7. `undo_added.py` (remove a recipe run by signature) - partly covered by `--replace` + snapshots.
