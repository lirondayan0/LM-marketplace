> HISTORY LOG (chronological, includes superseded rules). The CURRENT rules are in `section-drawings.md`; read that first, come here only for evidence/context.

# Convention set: Israeli structural office (user: civil/structural engineer), file `חתכים.dxf`

Source: user's own drawings in `Desktop\AI`. Confidence noted per rule. Add new rules here, with evidence; mark superseded ones.

## File facts
- Units cm (INSUNITS 5), plotted scale 1:25, text height 6, arrows 1, DXF AC1032. Sections live in Model space.
- Hebrew text is stored as English-keyboard characters in SHX fonts (`Sivan`, `HEBTXT`, `MIRYL`). Decode with the Hebrew keyboard layout (`dxflib.decode`); `&` = Ø in rebar notes; `%%U` = underline.
  Examples: `j,l` = חתך, `pbho` = פנים, `ju.` = חוץ.
- Section titles on `54_HATAH_TEXT`, format `%%Uj,l 3-3` (+ a "1:25" text and a note line below). User's "67-67" means section `76-76` (digit swap, verified once).
- Layer names are transliterated Hebrew: `HATAH`=חתך, `MIDA`=מידה, `ZIUN`=ציון, `ZET`=leader line for a note/rebar detail (user 2026-10-13; earlier guess 'rebar' superseded), `KIR`=קיר, `BARZEL`=ברזל. Full list of the office's 247 layers: skill `anthropic-skills:construction-layers`.

## Layers (sections)
| Element | Layer | Confidence |
|---|---|---|
| Cut outline | `5_HATAH _KONTUR` (note the space) or `9_KONTUR` — both occur | verified |
| Dimensions | `53_HATAH_MIDA`, style `dim_25` | verified |
| Rebar help lines | `2000_DOT_HELP_LINE` | 1 example |
| Rebar leaders | `56_HATAH_ZET` | 1 example |
| Stirrups | `57_HATAH_ZIUN` | 1 example |
| Level marker block `MH` ("o.k." arrow) | `58_HATAH_SIM` | 1 example |
| Section title/text | `54_HATAH_TEXT` | verified |

## Dimension convention for sections (from 76-76)
- Parts close to the section, ~15 cm off the outline; overall farther out, ~30 cm.
- Bottom: each part width (15) + overall width (30). Left: end thickness (15) + overall height (30). Right: every level step (15).
- Style `dim_25` has `dimexo=40` (extension lines hidden by default) → override `dimexo=1.5, dimexe=2.0` so extension lines show. Measured (not overridden) text.
- Applied (not independently verified by the user) to 1-1, 2-2, 4-4, 5-5 on 2026-10-03; the user has not yet confirmed that the result matches their intent.

## Open questions / oddities
- Two "65" dimension text overrides on 85-measuring dims in 76-76 look like leftovers; not copied.
- Sections with 1-1/2-2 style L shapes repeat the same value on the left (end thickness = overall height): kept per rule, user may want one dropped. UNVERIFIED preference.
- 5-5: break-line zigzag on the outline produced tiny dims (2–3.5 cm); desired handling not yet confirmed.
- Other drawing types in the folder (`פרטים וחתכים אוטומטים.dxf`, `שכבות.dxf`) not yet studied.

## Rebar in sections (consolidated 2026-10-04; sources: 76-76, 13 finished examples in the yellow box, the user's red clouds)
Automated by `recipes/rebar_section.py` (geometry) + `recipes/rebar_notes.py` (leaders/notes). Applied to 1-1..5-5; user said "excellent" but has not signed off each detail.

**Geometry** (verified: 76-76 reproduced exactly; 4-4, 7-7 of the examples)
- Help lines `2000_DOT_HELP_LINE` = outline inset 4.5, to the cut (break-line) end. A 7-cm-wide lip gets ONE line at 4.5 from the outer face.
- Bar dots = block `dot barzel` on `57_HATAH_ZIUN`: at help-line vertices, equal division, **max step 15 in every direction** (wall 20 -> 2x10, 115 -> 8x14.4, junction gap 11). Last dot 4.5 from a cut line. Junction dots on BOTH wall lines at both slab levels. (76-76's 21.25 stem step is the older exception.)
- Stirrup (`57_HATAH_ZIUN`): closed rectangle inset 3, hook polyline at top-right (-7.5,-6)(-2.2,0)(0,0)(0,-2.7)(-5.4,-8.6). Slab bar lines (57): top/bottom, inset 3, run THROUGH the wall to the stirrup's far side.
- Stirrup detail redrawn right of the section, same bottom y, width 14: gap **28.5 from a cut line**, **58.6 from a wall/edge face** (1-1, 2-2 vs 4-4, 5-5 and their starred twins; 76-76 had 45.8).
- From the user's red clouds: a free slab end is closed by a vertical bar (3-3); at a 7-cm lip the slab bar bends down into the lip along the outer face, 3 from it (4-4 bottom bar, 5-5 top bar). UNVERIFIED which bar in 5-5 / U-bar vs single bar in 3-3.
- No stirrup / detail where the member is 7 cm wide (5-5).

**Leaders and notes** (layer `56_HATAH_ZET`; text `54_HATAH_TEXT`, HEBTXT h=6; `&` = Ø)
- The dots ARE the bars; every leader forks to specific dots. Standard bar set in all examples: `2&12` corners top/bottom, `2&8@20` first side pair below the slab (middle pair for a wall above), `4&12` = top pair + slab-bottom-level pair, stirrup ` &8@15` + `L=n`, n = 2*(14+h)+14 (fits 1-1, 5-5, *4-*4; example 4-4's 136 looks stale).
- Fork = one 2-point polyline elbow->dot per dot; the lower pair of 4&12 is one V polyline; underline LINE from the elbow. T-sections: 4&12 and 2&12 left, 2&8@20 right. L/wall sections: notes on the outer side.
- Neat layout (user asked): one elbow column per side (gap 7 left / 9 right of the outer dot column), equal underline length 31.9, rows >= 12 apart, ordered top to bottom.
- Slab notes `ב.ע. לפי תכנית` / `ב.ת. לפי תכנית`: Sivan text with **text_generation_flag = 2 (mirrored)**, insert at the RIGHT end of the leader's horizontal run; polyline [(dot.x -+59.9, yh),(dot.x -+7.2, yh),dot]; yh = dot.y+28 (top, clears the o.k. marker; T-type +14.1) / dot.y-19.9 (bottom).
- Not placed where the geometry does not fit the set (3-3 raised edge, 4-4 7-cm lip, 5-5): ask the user which bars go where.

**Not yet reproduced from the examples**: detail dimensions (14 and height, `dim_25_BARZEL_Above` on 54), the second detail below the section (60x14 horizontal bar `&8@15 L=134`), the long level line with arrow at walls.

## Section geometry (from the plan), learned 2026-10-06 on `ramla.dxf` (Gallery 1 plan, Section 1-1)
- Units cm. A section is cut where the plan has `hat` blocks (layer `23_SIM`, attr A = number) at both ends of a cut line; arrow flag points the view direction (looking east: north = left, south = right).
- Beam label `30/65` (layer `451TEXT_KORA_100`) = width/total height; beam edges on `93_KORA`. Beam levels as text `o.k.-0.80=+69.70` / `u.k.` (top/bottom). Slab: block `S_M` (attrs `D=20`, `-0.15`, level text `-4.40=+66.10`) and text `D=20+5` / `D=25+7`.
- Reading used (UNVERIFIED on a 2nd case, user to confirm with clouds): slab thickness = FIRST number of D=a+b (ground-floor 1-1: D=25+7 -> slab drawn 25); `+b` = fill, not drawn. Edge beam: slab top flush with beam top, slab hangs on the right, 59 shown then break-line zigzag (example 1-1: wall 20, height 74, slab 25).
- Drawing recipe: outline = 5 LINEs on `9_KONTUR` (ltscale 5) + zigzag LWPOLYLINE on `5_HATAH _KONTUR`; title `%%Uj,l N-N` SIVAN h9 width .9 mirrored (flag 2) 77.4 above the top, `1:25` HEBREW_NEW h6 below-left of it. Automated: `recipes/section_outline.py`, then `dim_section.py --near`.
- Target boxes: the user draws white cells (layer `72_MISGERET_WIN`, 400x450) to the right of the plan and a red cloud around the cell to fill; 1-1 went in the leftmost cell. The user may save several versions: read the file they name, re-scan after each save.
- **View direction** of a cut = the `hat` block's local +y after its rotation (rot 270 -> east, 180 -> south, 0 -> north; negative xscale only mirrors). Looking east: south is right; looking south: west is right; looking north: east is right. Verified by the user's description of 1-1 (slab right, opening left).
- **Plan layout (Level -1 mezzanine, ramla.dxf)**: 4 hollow-core slab bays `D=20+5` (20 hollow-core + 5 topping, user 2026-10-06). Beams: `30/65` north/south edges (cut 1-1: slab on ONE side, opening on the other), `80/65` between bays (3-3: slab BOTH sides) and the slanted east edge (2-2: slab on one side), `65/65` west edge (4-4: slab one side, opening other). Section 5 = 25-wide wall/beam at the stair core (not yet drawn).
- Drawn 2026-10-06 with `section_outline.py`: 2-2 (80/65, slab right), 3-3 (80/65, slab both sides), 4-4 (65/65, slab right) in cells 2-4; slab 20 shown, as in 1-1. UNVERIFIED: whether the 5 cm topping should add to the drawn thickness (25) for hollow-core.
- **Dimension rule, user correction 2026-10-06 (red X marks on 1-1..4-4)** supersedes the 'bottom parts + overall' rule where a slab continues past a break mark: NO dimension for the variable slab length, NO overall bottom width, and no duplicate left overall (when the end thickness equals the total height). Kept: beam width, left end thickness, right level steps (slab thickness + below-slab depth). 3-3 (slab both sides): bottom 80 only; left 20 + 65; right 45 + 20. Automated as default in `dim_section.py` (`--full` restores the old behaviour); the output reproduces the user-approved hand state of 1-1 and 3-3.
- **'o.k per plan' level marker** (user's red cloud, 2026-10-06): block `o.k block` (layer `57_HATAH_ZIUN`; contains `MH` arrow + text `o.k` + mirrored Hebrew 'לפי תכנית' = per plan) with its arrow tip ON the beam top, ~beam centre + 9.5 (user placed it at +8.2 on 1-1 and +10.8 on 2-2). Added to every section (3-3, 4-4 by me); `section_outline.py` now adds it automatically. The user's X marks and clouds (layer `SHINUIM-TIKUNIM`) were left in place.

## Hollow-core beam sections (learned 2026-10-06 from the ground-floor example sheet at x~113146 on `ramla.dxf`; user confirmed the mapping)
- Slabs are hollow-core panels + cast topping: **ground floor D=25+7 (topping 7), mezzanine/gallery D=20+5 (topping 5)** (user). Drawn as panel band + topping band (dims `hb | S | T` and overall); my earlier flat 20-thick outlines were wrong and were replaced.
- **Ledge beam** (example 2-2: 80 wide x 75 = 43 below ledge + 25 panel + 7 topping): 15 ledge each slab side, 50 stem rising between the panel ends to the slab top, topping continuous over the stem; panels shown 45 beyond the beam face, break mark (zigzag from topping top +10 down to the panel soffit) at each free end. Panel bar dashes (`51_HATAH_DASHED`) 3 from panel faces; topping mesh line (`57`) at top-3, mesh dots at top-4: first 8.8 from the stem face, step 20, 3 per side.
- Reinforcement of the beam (example 2-2): help lines inset 4.5 (4.6 at the top and ledge levels), stirrup contour inset 3 (`2000_DOT_HELP_LINE`); dots (closed 2-pt polyline, bulge 1, d=1): bottom row 8 (step 10.15), top row of the stem 8 (step 5.9), ledge columns and stem columns 3 each (step <=17). Stirrups: two 60-wide U's over the ledge zone, two overlapping 30-wide rectangles over the stem (3 of 35 on an 85 stem, example 5-5); hook ticks at each tall rectangle's top-right corner. Notes: `&12@20` (stirrup, fork to both outer legs), `ב.ת. לפי תכנית` (bottom bars per plan, fork to 2 bottom dots), `ב.ע. לפי תכנית` (top bars per plan, fork to 2 top dots), `לפי תכנית` for each topping mesh. Longitudinal beam bars are NOT given numerically ('per plan').
- **One slab side** (ours 2-2, 4-4; opening on the other side): same recipe with the plain face full height; stirrup note moved to the free space beside the beam on the slab side. UNVERIFIED (no example with an opening).
- **Cast L edge beam** (example 1-1, generic B / D / H): dot columns at 4.4 and B-4.3 (5 per column on B=20,H=74), slab dots rows at slab-soffit+4.4 and top-4.3 from B+9.9 step 15; stirrup B-6 x H-6 at inset 3 with hook; notes `4Ø12` (top pair + soffit-level pair), `2Ø12` (bottom pair), `2Ø8@20` (mid pair), slab `ב.ת./ב.ע. לפי תכ'`; stirrup elevation drawn LEFT of the section (two halves, `Ø10@15`, dims B-6 / H-6). Used for our 30/65 beam (1-1) with D = 20 + 5.
- Bar COUNTS follow max-spacing rules fitted to the examples (UNVERIFIED for other widths/heights): the user chooses counts in the examples, they are not derivable.
- Not reproduced yet: the stirrup/bar shape details drawn under each example section (the `60`-wide detail row), the 2-level slab of example 3-3, example 5-5's left panel with cores.

### User corrections on the gallery hollow-core sections (2026-10-06, after reviewing my 3-3 / 4-4) - supersede the rules above where they differ
- **Rebar dots are SOLID**: closed 2-point polyline, bulge +/-1, **constant width = diameter (1.0)** (examples have const_width 1.0). Hollow circles (width 0) are wrong. (`add_dot` fixed, tested.)
- **One overall height dimension only**, on the slab side (right); never repeat it on the left (red X on the left 65 in 3-3 and 4-4). The left keeps the level dims `hb | S | T` only where there is a slab on that side.
- **Stirrup note symbol**: gallery beams use `$12@20` (user retyped `&` as `$` on 3-3, cloud around it; the ground-floor examples use `&12@20`). Applied to all gallery ledge beams, UNVERIFIED for 2-2 / 4-4 (user did not retype them). Diameter/spacing still copied from example 2-2.
- **Topping mesh note** reads `זיון לפי תכנית` (raw ` zhui kph ,fbh,`), not just `לפי תכנית`; leader higher: both slab sides -> elbow H+16.4 (left) / H+13.6 (right) from the dot nearest the stem; one slab side -> starts at the SECOND mesh dot, elbow 11.4 beyond it, 16.4 above the topping, 68.3 long.
- **Top-bars note** (`ב.ע. לפי תכנית`): both slab sides -> raised elbow H+25.2 at the stem's right face; **one slab side -> on the free plain side**, elbow 12.5 inside the first top dot and 14 above the topping, underline 61.4 to the plain side, forks to top dots idx 3 and last.
- Generator bug fixed: `--replace` kept old note texts, so a second run duplicated every note (4-4 showed two stirrup notes, the user crossed the stale one). Clearing now removes all texts except the section title and `1:25`; check for duplicate texts after any re-run.
- Unclear mark: a tiny red closed triangle at the bottom row of 3-3 around the third bottom dot (x ~ 24.5 from the beam face, y 4.5). Not acted on; asked the user.

### User corrections, round 2 (2026-10-06, user's hand edits of the gallery sections; diffed against my regenerated state)
- **Sections sit higher in the cell**: beam bottom 236.3 above the cell bottom (was 170); the room below holds the stirrup detail row (profile `cell_beam_bottom_y`).
- **Stirrup detail row under each section** (user built it on 3-3): left to right `[U over the left ledge] [tall stirrups] [U over the right ledge]`, drawn at the section's x positions, all on `57_HATAH_ZIUN`, dims and notes on `54_HATAH_TEXT`. Tall stirrups: the section's stem rectangles (30 x 59 = width x H-6), the 2nd offset (+14, -5.9) from the 1st, top of the 1st 74.5 below the beam bottom, hook ticks at the top-right corner (x-2.8, 4.3 high; 4.5 long at y-2.7), dims = width and height, note `2$12@15 L=190` with L = 2*(w + H-6) + 12, text 19.8 under the lowest edge, 6.7 left of the first rectangle. U stirrups: 60 wide x (hb-6) high (34), open toward the beam (left U open right, right U open left; left U ends at x=-19.1, right U starts 13.3 right of the beam face), top edge 113.3 below the beam bottom, dims 60 and 34, note `$12@15 L=154` with L = 60 + 2*(hb-6) + 26. One-sided slab: tall stirrups + one U on the slab side.
- **Spacing**: the detail notes say `@15`, the section's stirrup note says `$12@20` (both the user's; do not unify). **Symbol `$` replaces `&` in all gallery notes** (`4$12`, `2$12`, `$12@20`, `2$12@15`).
- **Stirrup note leader** (`$12@20`): elbow 12.7 above the beam bottom; fork ends on the outer legs at y=20.0 and 20.0 (both slab sides) or 23.2 (left) / 20.0 (right) (one slab side).
- **Cast L 1-1 reworked by the user** into a hollow-core edge: panel D-5 with **3 cores** (circles r=5, `5_HATAH _KONTUR`, 20 apart, first 8.3 from the stem face, centred 0.8 above the panel middle), topping soffit line at H-5 from the slab end back to the stirrup edge, **2 topping mesh dots** (y=H-4, first 7.4 from the stem, step 20) instead of the slab dot rows; notes: `4$12` forks to the TOP PAIR only; `2$12` bottom pair; the old `2&8@20` and the slab-soffit note `ב.ת. לפי תכ'` are deleted; the stirrup note `$12@20` forks from both mid dots to one elbow 4 right of the stem and 16 above the bottom; top-bars note elbow (B+45.8, H+16.5). The old elevation detail with `&10@15` was deleted (replaced by the detail row: one rectangle B-6 x H-6, `$12@15 L=2*(B-6+H-6)+12`).
- Not reproduced from the user's edit: the 3-3 title moved 20 right (probably layout taste), small dimension text moves.
- Re-running a section over a hand-edited cell (`--replace`) now also removes the user's anonymous-block details (`*U...`) and circles, then redraws them: first diff the user's version against the last generated one and fold every correction into the recipe, as done here.

### User corrections, round 3 (2026-10-06): how to dimension the stirrup details ('rims')
- Source: the red cloud on the vertical `34` of the right U in 3-3 (+ the user's raised `60` above it and a scratch stirrup 14 x 57 with `dim_25_BARZEL` dims). The ground-floor example details use the same family of styles: `dim_25_BARZEL` (text only: dimension line, extension lines and arrows suppressed) for horizontal bars, `25_BARZEL_Below` (note the name) for vertical legs, aligned dims whose points lie ON the bar.
- **Rule applied to every U and tall stirrup of every section**: the vertical leg length (34 / 59) = `dim_25_BARZEL` aligned dim ON the leg, text OUTSIDE the closed edge (right U: east, left U: west, tall stirrup: east of its right edge); the width (60 / 30) of a U = plain `dim_25` (ticks) 13.5 ABOVE the bar with the dimension points on the dimension line (no extension lines); the tall stirrups' width dim stays on their bottom edge (user did not change it).
- The 14 x 57 stirrup with a polyline hook in cell 3 is the user's scratch/model; recipes keep it (`--dims-only` only touches the detail row's x-range). Open question to the user: should it become part of the standard detail?
- Aligned dim text side: it goes to the LEFT of the direction p1 -> p2 (to put the text outside the right edge, measure top -> bottom).

### Round 4 (2026-10-06): final dimension rule for the stirrup details - SUPERSEDES the 'raised 60' part of round 3
- The user corrected 3-3: **every dimension of a bar shape is text-only `dim_25_BARZEL` written ON the bar**: U width on the U's top edge (text above the edge), tall-stirrup width on its bottom edge (text above, inside), vertical legs on the leg with the text outside the closed edge. Exactly the ground-floor example convention; no ticks, no raised dimension lines anywhere in the detail row. Constant `DIM_RAISE` removed from the profile.
- The user deleted their scratch 14 x 57 stirrup with the polyline hook: the two-tick hook (x-2.8 / 4.3 high, 4.5 long at y-2.7) stays the standard.
- After the restyle our output differs from the user's 3-3 only in the vertical text position of the two '30' (they nudged them ~2 units down by hand): ignored.

## 2026-10-15 star markers (sections_ramla.dxf) - evidence
- First pair (south edge 30/65 looking E) -> mirror cast L, slab LEFT, placed beside the plan at the cloud; user: "excellent". Batch 2: 8 pairs grouped 1-1 (4 south, slab left), 2-2 (4 north, slab right), 3-3 (80/65 ledge). Then the user: "orient clockwise" -> south pairs turned to look W, all 30/65 edge beams merged into 1-1 (8 beams), 80/65 = 2-2 (this superseded the left/right split).
- Red cloud 1: user's own turned pair = 180 deg turn + centred on the beam axis + east of the label. Red cloud 2: attribute number moved by its text height (ly 11.9 -> 29.97). Both reproduced by star_orient.py.
- Batch 3 (2026-10-15, sections_ramla.dxf): pair at (81004,33623) looking N across the W edge beam 65/65 (N-S), D=20+5 east = slab right, LENGTHWISE -> `ledge_beam.py --kind ledge --sides right --beam 65 65 --slab 20 --topping 5` = section 3-3 in cell 3 (orientation already clockwise). Pair at (79565,34570) looking N: no beam under it - only the free east edge of a small D=20 slab (9_KONTUR) and a 25 strip further west -> NOT drawn, reported, asked (no taught section for a free slab edge).
