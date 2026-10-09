# Structural PLAN dimensioning - CURRENT rules (consolidated 2026-10-08; evidence + superseded rules: history-plan-dimensions.md)
Sources: the office example `לימוד כללי\דומגא לתוכנית מידות.dxf` (finished plan, style dim_50) and the user's marks / hand edits on `ramla_base-dimplan.dxf` (style dim_100). Confidence: 1 example plan + 8 rounds of user corrections.

## Style
- Layer `36_MIDA_CLALI`, style `dim_50` (1:50) / `dim_100` (ramla_base), measured text only, linear dims at 0 / 90 (aligned or rotated-linear only for skewed things), face to face, never axes.
- Text never upside-down (direction p1->p2 in (-90,90]); no dim shorter than 8.

## Structure (what a worker should see)
0. USER PRIORITY (restated 2026-10-08, gallery plan): ONE continuous line wherever possible; after generating, always run a merge pass (`merge_chains`) over nearby same-axis lines and look for parallel short lines to join.
1. CONTINUOUS chains: one dim line = items wall | clear | wall | opening | wall ... (typical walls 20/25/30). As few separate lines as possible; a chain crossing a wall or pier carries its item (fill the hole: horizontal 40.2 through a skewed pier, 20 / 10.4 jogs).
2. Outer chains (office example): one overall per side, then a chain of the main parts, then the detail chains.
3. Pit / shaft blocks (93_KORA frame + wall polygons): the user's example chains (3 vertical face chains, items between the vertices of each wall line, ~92 off the west face) + overall height; the same on every block. Openings between wall pieces are items of those chains (e.g. y=27185: 25|240|25|140|25|240|25); a jog pair counts once.
4. Rows / columns of skewed piers: ONE linear dim line along the row (offset 80, west of columns / south of rows): pier extent | clear gap | extent ...; thickness comes from the crossing chains (never a second aligned dim). Single pier outside a row (104E): length + thickness next to it (offset ~80, must not cross a chain).
5. Skewed rooms / tanks (> 1100 long): aligned clear length + ONE vertical chain wall | clear | wall (user: x=81862 on 108C); E/W wall thickness aligned.
6. Odd single elements (pentagon rooms, orphan rectangles, hidden 15_DASHED rectangles): the missing edges only; thin hidden rectangles (<= 50) length only; dashed non-rectangles repeat a wall polygon -> skip.
7. No diameter dims on circles. Building outline, annotation frames, pit-block interiors beyond the user's example chains: not dimensioned individually.

## No duplicates
- A feature is dimensioned ONCE. If a chain item measures it (same faces, value within 0.6 %), the separate dim goes (35 of 108E, 40 of 1047/102D/1048/1049, tank clear width and N/S walls). Same two faces twice on the same element: delete one. Old user dims are only removed when clouded or exact duplicates.

## Text placement
- A narrow item (<= 150) whose text would sit on a wall hatch: the text moves ALONG the line beside the wall (up / right first), centre = item centre + item/2 + text half width + 12, perpendicular 23, same side as before (user's yellow-cloud example: the 20 at y=29626). Narrow spans elsewhere: texts alternate above / below (+-45).

## Cloud colours (layer SHINUIM-TIKUNIM; the user recolours between saves - re-read every time)
- RED (no colour override) = example to DELETE (generalise to the whole plan). BLUE (ACI 4) = example to ADD / ADJUST. YELLOW (ACI 2) = model example: copy this treatment everywhere. ACI 114 (green) = meaning UNKNOWN - leave and ask. Clouds stay in the file (the user removes them).

## Pipeline (recipes, in this order; all in place, `--box` = one plan only, `--expect` = abort if the user saved meanwhile)
`plan_chains.py` (pier / wall chains) -> `plan_elements.py` (blocks, orphans, building overall; first pass, writes a copy) -> `plan_revise.py` (cloud-driven one-off revision) -> `plan_continuity.py` (holes, duplicates, row / tank chains, wall-text shift) -> `plan_review.py` (inspector: missing sizes, openings). A slab / gallery plan inside a bigger file: `plan_gallery.py` (box-limited chains + merge into continuous lines + void + overall), `--replace` to re-run. `plan_tidy.py` is SUPERSEDED (its G2 / G3 deleted what the user wants).

## Self-check before reporting
Coverage audit (every element size readable) - text upright - no duplicates - openings dimensioned - texts off walls - diff vs the user's last save shows only intended changes - audit 0 errors - tests pass - report counts and what is UNVERIFIED.

## Gallery / mezzanine plan (ramla_base-dimplan.dxf, 'גלריה 1-', 2026-10-08) - UNVERIFIED, first pass
- Same dim_100 rules as the basement plan; recipe `plan_gallery.py`. Cores (lift/stair/MAMAD) are covered by the wall-slicing chains, no separate block chains. Bay notes (rebar texts) sit on the default row lines -> the line moves to the other pier face. Void ('חלל כפול' hatch) = extra items in existing chains. Beam sizes stay as the existing labels (30/65). Not dimensioned: piers at x>85000 outside the slab contour, levels.
- CONTINUITY ON THE GALLERY PLAN (user, red cloud y 41428-41644, 2026-10-08): two row chains on nearly the same line (y 41495 + 41566, piers of two staggered rows) must be ONE dim line. Rule: chains of the same axis whose lines are < 450 apart are merged when their items do not conflict (finest item wins, exact duplicates measured once, overlapped clear spans dropped and re-filled, a pier overlapped by a narrower one is trimmed e.g. strip 150 -> 110 + pier 40). Implemented in `plan_gallery.py` (`merge_chains`, `--replace`). Generalises the 'as few separate lines as possible' rule; 450 is a guess (UNVERIFIED).
