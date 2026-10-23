# The user's gallery of hollow-core / slab-to-beam section geometries (2026-10-15, sections_ramla.dxf, red cloud x 93869-100103, y 62809-63503)
18 anonymous blocks (`*U...` INSERTs on layer `5_HATAH _KONTUR`, no attributes) = finished SECTION DETAILS drawn by the user, each with its own outline, rebar dots (`57_HATAH_ZIUN`), notes (`56_HATAH_ZET` leaders, `kph ,fbh,` = "per plan"), dims (`53_HATAH_MIDA`). Read by walking the block (`doc.blocks[name]`); outline = polylines on `5_HATAH _KONTUR` (existing / precast) or `9_KONTUR` (NEW cast-in-situ, green). Break marks (zigzag) = slab continues. Circles r=5 = hollow-core CORES seen in section (panel runs ALONG the beam). Coordinates below: main outline from its bottom-left, cm.
Reading UNVERIFIED unless the user confirms; the numbers are exact (dims inside the blocks).

| # | Type (reading) | Geometry |
|---|---|---|
| 0 | ledge beam, panels both sides, symmetric | beam 100 x 60, stem 70, ledge 15 each side, ledge top at 23; panel 30 + topping 7 |
| 1 | ledge both sides, DIFFERENT levels | H 65, stem 85, left ledge 15 (top 33, panel 25 + 7), right ledge top 40 (panel 25) |
| 2 | ledge LEFT only, plain right face | H 65, 15 ledge top 35, panel 25 + 5, stem 85 |
| 3 | ledge both sides, different panel thickness | stem 80, H 65: left panel 30 on ledge top 35, right panel 20 on ledge top 45 |
| 4 | ledge RIGHT only | stem 80, H 65, panel 30 on ledge top 35 |
| 5 | transfer beam H 100: LEDGE one side, CORES other | stem 65 + ledge 15 left (panel 20 + 5, ledge top 75); right: cores panel 25 + 7 (2 circles), top 68 |
| 6 | H 80: lengthwise panel left, CORES right | stem 80; left panel 25 + 7 on 55; right cores panel (circles) 25 + 7 |
| 7 | H 80: CORES both sides | stem 80; left panel 20 + 5? (circles), right 25 + 7 (circles) |
| 8 | cast edge beam with CORES one side | H 70, stem 80 plain right; left cores panel 30 + 5 over 35 |
| 9 | NEW cast T / rib under a solid slab | solid slab 25 both sides (zigzag breaks) + rib 20/25/30 wide, 40 deep (total 65) |
| 10 | NEW cast rectangle | 20/25/30 x 40, 8 bars |
| 11 | NEW cast L rib | solid slab 25 one side + rib 20/25/30 x 40 (total 65) |
| 12 | NEW cast slab step | slab 20 + 30 (H 50), step 15 at the right, 2&14 |
| 13 | tall beam H 90, stem 100, slabs at DIFFERENT levels | left slab 25 at top; right panel 30 / 40 lower |
| 14 | H 80, stem 80 | left slab 25 at top (55 below), right 25 at the 50 level |
| 15 | H 100, stem 80 | left ledge low (30 / 20), right: two slab levels (40 and 30 stacked) |
| 16 | UPSTAND beam (slabs at the BOTTOM of the stem) | H 100, stem 80 rises 75 above a 25 slab level, slabs both sides low |
| 17 | upstand beam, asymmetric | H 100, left slab low 20, right slab 40 at the 25 level + second slab |

## What this teaches (for the planner / recipes)
- A side is one of: ledge + lengthwise panel (hollow-core ON the ledge), ledge + CORES (circles: panel runs past), plain face, solid cast slab (zigzag, no ledge), or slab at ANOTHER level. A beam may combine different kinds on its two sides (#5, #6): my recipes treat both sides alike (`--sides` + one `--kind`) - a per-side kind is the missing generalisation (ledge_beam has `--solid` since 2026-10-15; cores on one side + ledge on the other is NOT yet drawable).
- Levels differ side to side almost everywhere (ledge tops 23..75, panel 20..30, topping 5/7): heights come from the plan labels (`o.k` levels, `D=a+b`), never defaults.
- Upstand beams (#16, #17) have the slab at the BOTTOM of a tall stem: the existing recipes (slab at the top) cannot draw them.
- Stem width is the plan's b; ledge width is 15 (#0..#5), cast ribs 20/25/30 are generic widths (labelled `20,25,30`).

## Cross-check of plan C sections 3-3 / 4-4 against the gallery (2026-10-15)
- Block #14 (H 80, stem 80) = the 4-4 pattern: right slab 30 thick FLUSH with the beam soffit, its top 50 below the beam top, hollow ledge 25 on the other side; the stem rises above the low slab like an upstand (#16 / #17 = same idea with taller stems). So `--solid-drop` with D + drop = H is a taught shape, not an accident.
- Each slab side carries its OWN dimension chain (below / slab / above), the overall height on one side (#1, #13, #14, #16): `ledge_beam.py --solid` now draws that chain (before: only D and the step).
- Hollow side: below-ledge + panel + topping = beam height (#7: 48 + 25 + 7 = 80): my S + T rule is the user's.
- ANSWERED by the user (2026-10-15): a plan label `D=10` at a higher level (`+0.00`) above a `D=30` slab = a RAISED (double) FLOOR of 10 cm: not structural, NOT drawn in sections; the structural slab is the `D=30` one.
