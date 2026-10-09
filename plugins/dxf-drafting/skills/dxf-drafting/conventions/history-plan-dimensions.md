# HISTORY (chronological evidence incl. superseded rules) - CURRENT rules are in plan-dimensions.md

# Structural PLAN dimensioning (learned 2026-10-08 from `לימוד כללי\דומגא לתוכנית מידות.dxf`)
Evidence: one finished example plan (ground/gallery floor, Model space, cm, ~2200 x 2070 extent, 403 dims). Confidence: 1 example, rules below are OBSERVED, not yet reproduced by a recipe.

## Style / layer
- All dims: layer `36_MIDA_CLALI` (ACI 2 yellow), style `dim_50` (plan scale 1:50: text 12, arrows 2 ticks `DIM`, dimexo 1, dimexe 1, dimdec 0, measured text - ZERO text overrides). `dim_25` is for sections, not plans.
- Only linear dims, angle 0 (horizontal) or 90 (vertical): 186 H, 213 V, 3 angled (at the slanted corner), 1 aligned.

## Chain structure
- Dims are CONTINUOUS CHAINS (each dim's start = previous end) along a common dimension line; a chain follows one grid/cut line across the plan and measures wall thickness, opening, wall thickness... (e.g. 20, 190, 25, 150, 25, 155, 25, 200, 25). Typical wall values 20/25/30, openings free.
- Many chains inside the plan (one per structural band, y/x levels ~100-250 apart), PLUS exterior chains:
  - Outer-most: ONE overall dim per side (2205 horizontal top and bottom at y 135122 / 132799; 2197 left x 24711; 2070 right x 27239).
  - Next inward: a chain of the main parts (bays/axes: 334, 403, 92, 156, 159...) at ~29 from the overall (y 132828 vs 132799); top mirror at y 134991.
  - Then the detailed wall/opening chains, inside or across the plan.
- Vertical outer chains: x 24711 (overall), 24737 (4 sub-parts), 24983.. (details); right side x 27239 overall, 27189/27108/27036 sub chains.
- Dim line is placed OUTSIDE the element for outer chains, and ACROSS the plan (through rooms) for inner chains; text above the line (dimtad 1) and not overlapping other text.

## Where extension points snap (806 points checked)
- 470 on `82_KIR_OLE` (wall outline edges), 155 on `93_KORA` (beam edges), 77 on `6_HATCH`, 76 on `9_KONTUR`, 20 on `8_KIR`; 222 on no vertex (intersections of wall lines with the chain line, or mid-wall).
- So: dimension FACE to FACE of walls (thickness + clear opening), never centerlines/axes.

## Not yet learned (ask / verify with the user's marks before automating)
- Rule that decides which walls get a chain, the exact offsets between exterior chains (observed ~29), treatment of slanted walls (3 angled dims), whether small values (10, 15) are kept. Level/elevation tags and slab-label texts are separate (`4_TEXT`, `23_SIM`).

## Site dimension plan for ramla_base.dxf (2026-10-08, user: "dimension ALL elements so the on-site worker can build, aesthetic and accurate, shifting allowed")
- Done by `recipes/plan_elements.py` on top of `plan_chains.py` output; style `dim_100` (1:100 base plan), layer `36_MIDA_CLALI`.
- Shaft/pit block = 93_KORA frame (720 x ~1700) + its 82_KIR_OLE wall polygons: parts chain of EVERY wall face 101 out of the block edge (south x / west y, else shifted or opposite side), overall one clear step beyond; narrow spans (<45) alternate text above/below the line.
- Skewed piers/stubs: thickness + length aligned dims, same side and offset for the whole family, plus one pitch chain along the row (lowest corners). Circles: diameter. Building: overall bbox south + east.
- Not done (listed in the report): arc wall (SW), 4 big polygon outlines (ramp/slab edges), circle positions (no grid), `15_DASHED` circles, notes/levels.
- Still UNVERIFIED by the user - confirm or correct with clouds, then fold into this file.

## Tidy rules (user's red clouds on ramla_base-dimplan.dxf, 2026-10-08; goal: FEWEST dimensions with every element still dimensioned)
- No diameter dims on circles. No size dims (thickness/length) on the skewed east piers (they carry the pier-type tag; only the clear spans between piers stay, user re-measured the pitch dims to 540 = pitch - pier length).
- Shaft/pit blocks: only the overall width/height; no per-face chains (north, side or south) - the continuous pier chains crossing the block carry wall thickness and room spans (UNVERIFIED: after this only ~half of the interior face gaps are measured by a dim; user to confirm).
- Never measure the same two faces twice (duplicates of the older/user dims go, e.g. my stub 120/35 vs their E35/E40; my 372 room width vs their 371.7).
- Old (user-approved) chain dims are only removed when clouded. Automated: `recipes/plan_tidy.py`.

## Cloud colours (user, 2026-10-08) - supersedes the tidy rules above where they differ
- RED cloud (layer SHINUIM-TIKUNIM, no colour override) = example of a dimension to DELETE; BLUE cloud (ACI 4) = example of a dimension to ADD or ADJUST. The user may recolour clouds between saves.
- Blue examples seen: (a) block B's three vertical face chains (one per wall line, items between the vertices ON that line, ref at the face, line ~92 off the west face) -> every pit block gets the same; (b) skewed-pier size dims: length on the west side (offset ~80-85), thickness below (offset ~77), aligned to the pier edges -> EVERY skewed pier gets both (so the earlier 'no size dims on skewed piers' rule was WRONG); (c) 104E thickness dim far away and crossing the 1008|639 chain -> a size dim sits next to its element (offset ~80) and must not cross another chain.
- Red examples seen: block north chains, face chains outside the examples, old horizontal 40.2 / 34.8 size dims of skewed piers (replaced by the aligned ones), the 40 under a pier that another chain already measures, diameters on circles (no Ø dims).
- Still true: never measure the same two faces twice; old user dims are only removed when clouded or exact duplicates.

## Readability + inspector rules (user, 2026-10-08)
- No reversed dimensions: text must never be upside-down (aligned dim direction p1->p2 must lie in (-90,90]; swap points and negate the offset otherwise). Check: dim geometry block TEXT/MTEXT rotation not in (90.5,270.5).
- Inspector pass: fewest dims, but every element's every size must be readable (chain connecting both faces, or aligned dim on a skewed edge; opposite edges of a parallelogram = one dim). Skewed tanks: clear L + W + wall thickness on each side. Pitch between skewed piers only when no clear-gap dim exists (gap + pier length = pitch).
- OPENINGS (user, 2026-10-08): where two wall pieces on one face line leave a gap (door / pass-through, e.g. 125, 140, 190 in the pit blocks) the gap is dimensioned as one more item of the EXISTING dimension line of that wall's chain, not on a new line; only if no existing line is free within ~150 a new line beside it. A jog pair (two faces < 40 apart, same interval) is one opening, one dim.
- Thin hidden (15_DASHED) rectangles <= 50 wide: dimension the length only (user deleted the 40 across).
- Self-check list before reporting: (1) coverage audit, (2) text never upside-down, (3) no dim measured twice, (4) openings dimensioned, (5) only intended entities changed (diff vs the user's last save), (6) audit 0 errors, tests pass.

## Continuity + no duplicates (user corrections, 2026-10-08) - CURRENT, supersedes the separate size / pitch dims above
- Prefer ONE continuous dim line (items: wall, clear, wall, opening ...) to individual dims. A chain with a hole (a pier/wall crossed by the line) gets the missing item (horizontal 40.2 through a skewed pier).
- A feature is dimensioned ONCE: if a chain item already measures it (same faces, same value within 0.6 %), delete the separate aligned dim (thickness 35 of pier 108E, 40 of 1047/102D/1048/1049, tank clear width and N/S walls).
- Rows/columns of skewed piers: one linear dim line along the row at offset 80 (west of columns / south of rows): pier extent | clear gap | pier extent ...; no corner-to-corner pitch dims; thickness comes from the crossing chains.
- Tanks: one vertical chain wall | clear | wall (user: x=81862 for 108C), ends on the real faces; aligned clear length stays.
- Openings between wall pieces: items of the same chain (user's y=27185 chain: 25 | 240 | 25 | 140 | 25 | 240 | 25).
- No dims < 8 (rounding artefacts). ACI 114 cloud (green) = meaning not yet known (UNVERIFIED): leave dims in it untouched and ask.
- WALL TEXTS (user, yellow cloud 2026-10-08, example: the 20 on y=29626 at x=78152): the continuous line includes the wall's own item; its text is shifted ALONG the line beside the wall (to the right / up; centre = wall centre + item/2 + text half width + 12, perpendicular offset 23 from the line, same side as before) - never on the hatch. Applies to every chain item whose text would sit on a wall (items <= 150). Cloud colours so far: red = delete, blue = add/adjust, yellow (ACI 2) = model example to copy everywhere, ACI 114 = unknown.
