# Recipes and scripts - one line each, grouped by job (rewritten 2026-10-23; keep in sync with the files)
Every recipe: office constants come from `../profiles/*.json` (`--profile NAME`; the legacy rebar recipes keep theirs inline), `--dry` previews, in place with a timestamped `.bak-*` snapshot first (`-o OUT` = optional separate copy, for tests / dry runs only), `--png` renders. Helpers: `../scripts/dxflib.py`. After changing a recipe, helper or profile run `python tests/run_tests.py` (+ `python tests/test_xref.py`) and add a test per new rule. FLAT layout: the DimPlan app copies `recipes/ scripts/ profiles/ assets/` as they are and puts `recipes/` and `scripts/` on `sys.path` - do not move files into sub-folders (except `legacy/`).
Status: **ACTIVE** = use it; **LIB** = imported by other recipes, do not delete although its own pipeline is superseded; **SUPERSEDED** = kept for reference / tests, do not use for new work; **LEGACY** = first-generation, in `legacy/`.

## 1. Entry points (one command per job)
| Command | Does | Status |
|---|---|---|
| `sections_round.py FILE [--dry] [--side ..] [--first N] [--png OUT]` | Whole standard section round: orient, plan, free space, draw, finish passes, arrays, coverage, audit, PNG (conventions/sections-workflow.md section 4). `--dry` still re-orients and SAVES. | ACTIVE |
| `../scripts/ref_library.py build REF ORIG` / `list` | Reference library of his hand-drawn XREF sections (`assets/ref_library.json`); `xref_overlay` uses it through `resolve()` for outlines with no taught rule (conventions/sections-xref.md section 7). | ACTIVE |
| `array_arrows.py FILE --box X0 Y0 X1 Y1 [--dry] [-o OUT]` | Loose bar dots follow their leader arrow: last bar on the tip, equal spacing (run before `bar_arrays`; conventions/sections-workflow.md section 8). | ACTIVE |
| `section_indicator_layer.py FILE [--dry] [--layer 23_SIM] [-o OUT]` | Moves every numbered `hat` section indicator to layer 23_SIM (snapshot first; star marks untouched). | ACTIVE |
| `plan_round.py FILE [--scan] [--write]` | Whole mark-driven plan-dimension round: scan marks, `plan_xlines` -> `plan_clouds` -> `plan_repair`, verify, `--write` (snapshot + mtime check + deletes the claude_DIM Xlines) (conventions/plan-dimensions.md section 2). | ACTIVE |
| `xref_overlay.py FILE [--only N,N] [--plan-dxf PLAN.dxf] [--dry] [--png] [--write] [--keep-marks] [--all]` | XREF section round, step 1 (conventions/sections-xref.md); `--all` only on an explicit 'all sections'. | ACTIVE |

## 2. Section planning and drawing (standard files)
| Recipe | Does | Status |
|---|---|---|
| `star_orient.py FILE [--max-y Y] [--tidy W] [--dry]` | Turns horizontal-beam star pairs clockwise (rigid 180 deg incl. numbers, centred on the beam axis); vertical-beam pairs untouched; snapshot first. | ACTIVE |
| `star_plan.py FILE [--kontur] [--first N] [--cells-at X Y] [--make-rows N] [--stirrups standard\|transfer] [--min-y/--max-y] [--draw]` | PLANNER of the whole star chain: per pair the evidence (view, strip, B, tag, ledge, transfer, D, CORES / LENGTHWISE, per-side slabs, wall cut, free edge, shutter) and the recipe + arguments; groups identical beams, numbers clockwise; `--draw` executes into the rows of 10 and renumbers the marks. Without `--draw` it never writes. | ACTIVE |
| `ledge_beam.py FILE N-N --box X Y W H --beam W H --slab S --topping T --sides both\|left\|right [--kind ledge\|cast] [--stirrups standard\|transfer] [--detail plan\|ss] [--replace] [--dims-only]` | Hollow-core beam section: ledge beam, cast L edge beam (cores = obrounds), solid slab beside it, stirrup detail row, notes, dims; reproduces example 2-2 (`tests/selftest_ledge_beam.py`). Also `finish` (sivan + leader_fit + rebar colour), `clear_cell`, `core_row/obround`, OVERLAY mode for XREF. | ACTIVE |
| `general_beam.py FILE N-N --box X Y W H --B b --D d [--H 40] [--h-label h] [--D-left/--D-right/--drop-left/--drop-right] [--d-label[-left/-right] H] [--sides left\|right] [--stirrups ..] [--detail ..] [--replace]` | The user's general cast beam + solid slab (6-6 family): wide-beam bar rows, middle steel by area, side dimension chains, side-face fill rows, mid-note placement, no restraint mesh; untagged beams (symbol `h`); reproduces 6-6 entity for entity. | ACTIVE |
| `slab_edge.py FILE N-N --box X Y W H --slab D [--d-label H] [--cut X Y] [--shutter B H] [--replace]` | Free slab edge: his 4-4 detail, thick edge (D >= 60: edge bars, bench copy; NO mid mesh since 2026-10-24), roller-shutter downstand. | ACTIVE |
| `beam_shutter.py FILE --face-x X --beam-bottom Y --slab-top Y --soffit Y --b B --h H [--side right] --h-dim-x X [-o OUT] [--dry]` | Roller-shutter downstand UNDER a general beam with slab both sides (his korchakk 6-6 hand edit: outline, closing bar, dot array, `2$10` note away from the stem, dims, numeric L stirrup, no in/out boxes; no o.k. marker). Reproduces his state (test). | ACTIVE (1 example) |
| `slab_step.py FILE N-N --origin X Y` | Slab-step section 70 (transformation slab) / 25 (standard): draws his 16-16 PARAMETRICALLY (`build(thick, thin, mirror, overlay)`, reproduces it at 70/25; `--stamp` = exact copy from `assets/slab_step_example.dxf`). The round places it itself (`star_plan` finds a no-beam S pair with a wide tag, `slab_step.layout` centres it in the cell). `scripts/extract_template.py` makes such a template from any box of a DXF. | ACTIVE (1 example, template) |
| `redraw_general.py FILE SPEC.json` | Redraw general-beam sections in place in their frames (origin kept, optional dx nudge), then run the finish passes. | ACTIVE |
| `slope_label.py FILE (--box X0 X1 Y0 Y1 --side .. --kind cast\|hollow \| --json J)` | 'Sloped slab' label + arrow on the slab (label only). `--json FILE.slopes.json` = the batch the round writes (`star_plan` finds the slope note itself, `sections_round` runs this after sivan_text). | ACTIVE |
| `scripts/transfer_check.py FILE X0 Y0 X1 Y1 [--pairs]` | New elements standing on a beam strip (informational since 2026-10-16). | ACTIVE |
| `scripts/cut_crossings.py FILE --box ..` + `scripts/plan_cuts.py FILE [--box ..]` | What each cut crosses (93_KORA / 0_LUHADIM_SHEN / 15_DASHED) and CORES / LENGTHWISE per cut - review every section against the plan. | ACTIVE |
| `scripts/shx_width.py` | Real SHX text widths (shelf = text). | ACTIVE |

## 3. Section finishing passes (run by sections_round in this order)
| Recipe | Does | Status |
|---|---|---|
| `sivan_text.py FILE --box ..` | Hebrew notes -> SIVAN (width 0.7, mirrored, standing on the shelf); notes with `$` -> HEBREW_NEW. | ACTIVE |
| `leader_fit.py FILE --box X Y W H [--dry]` | Shelf = text width, text on its shelf, fork tips on dot centres, orphan shelf gets forks. | ACTIVE |
| `rebar_color.py FILE --box ..` | Layer colours from his table; clears entity overrides; defines missing layers. | ACTIVE |
| `mid_note_fit.py FILE [--box ..] [--dry]` | Moves every middle-steel note to the nearest position that overlaps nothing. | ACTIVE |
| `ok_marker.py FILE --own --box X Y W H` | EVERY section cell of the sheet box (72_MISGERET_WIN frames) gets MH + 'o.k' + 'per plan' (SIVAN); old `o.k block` replaced; a cell with an MH is left alone (sections-workflow.md 5). `--cells .. --once K` = the old once-per-sheet block, superseded. | ACTIVE |
| `fit_rows.py FILE [--near X Y] [--dry]` | EVERY framed row of the stack: grows too-low rows downward (rows below move), all cells of a row on ONE title line, margins >= 25. Run by sections_round. | ACTIVE |
| `align_row.py FILE --near X Y` | One framed row only, on ONE title line (superseded by fit_rows for sheets; its +-60 band mixes neighbouring rows). | ACTIVE |
| `cell_dupes.py FILE [--fix]` | Finds / deletes doubled entities in the framed rows. | ACTIVE |
| `text_overlap.py FILE [--fix]` | Finds / fixes overlapping notes (stacked bottom notes are staggered). | ACTIVE |
| `bar_arrays.py FILE --box X0 Y0 X1 Y1 [--dry]` | Bar dots -> associative arrays via accoreconsole (PowerShell); LAST write step. | ACTIVE |
| `section_visibility.py FILE --box X0 Y0 X1 Y1 [--fix]` | Visibility gate for drawn sections: layers used in the box ON / thawed / unlocked, arrays on 57_HATAH_ZIUN, a visible title; `--fix` repairs (snapshot, idempotent). Run by sections_round + the app. | ACTIVE |
| `center_titles.py FILE [--min-y Y] [--max-y Y]` | Title block per section: title on the cell centre line + 26, the `1:25` centred under the VISIBLE title (called by `star_plan --draw`). | ACTIVE |
| `legacy/section_gaps.py`, `legacy/bar_anchor_marked.py`, `legacy/mid_steel_sheet.py`, `legacy/restagger_stirrups.py` | One-off passes with the brenda_karka path typed in (they run on import: moved to `legacy/` 2026-10-25, not for new work). Manual sheet passes (100 cm gaps; one-off cloud-driven bar entry 60 (the rule is in the generators now); re-space middle-steel dots + notes; redo stirrup counts). Carry sheet constants: re-derive per file (roadmap 3). | ACTIVE (manual) |
| `legacy/side_chain_dims.py`, `legacy/stem_side_dims.py`, `legacy/align_titles.py`, `legacy/center_sections.py` | Earlier sheet passes with brenda_karka constants, replaced by `general_beam` dims, `align_row`, `section_gaps`. | SUPERSEDED |

## 4. XREF sections (order: overlay -> extend_bars -> extend_dots -> text_clear -> [cores] -> arrays -> marks deleted)
| Recipe | Does | Status |
|---|---|---|
| `xref_extend_bars.py FILE [--dry]` | Slab bars to the XREF slab end (far end; idempotent). | ACTIVE |
| `xref_extend_dots.py FILE [apply]` | Dot rows follow the extended bars (spacing 20, last 0.7 from the end); before the arrays. | ACTIVE |
| `xref_text_clear.py FILE [--dry] [--vertical] [--gap 1.5]` | Notes slide left / right with stretched leader, never over XREF text / lines / other notes; leader never cut; `--vertical` = reported fallback. | ACTIVE |
| `xref_cores.py FILE [--only ..] [--dry] [--write] [--expect MTIME]` | Hollow-core voids (green obrounds) when he asks for them. | ACTIVE |
| `xref_wall.py`, `xref_junction.py` | Wall above a beam (his Sec 9, reproduced to 0.1); wall / slab junctions (my judgment, UNVERIFIED). Called by xref_overlay. | ACTIVE |

## 5. Plan dimensioning (conventions/plan-dimensions.md)
| Recipe | Does | Status |
|---|---|---|
| `plan_xlines.py FILE OUT [real] [--replace]` + `plan_xlines_lf.py` | Xline-driven chains clipped to the boundary (`kontur_analyze`, `dim_template`, `install`), orange clouds; library + CLI behind `plan_round`. | ACTIVE |
| `plan_clouds.py FILE OUT [real] [--aci 256 1] [--reach 600]` | Red-cloud additions INTO the nearest chain (`--companion` rejected, only if asked). | ACTIVE |
| `plan_repair.py IN OUT` | Text collision repair (X, Y, rotated dims), style-aware text offset. | ACTIVE |
| `plan_restyle.py FILE OUT`, `plan_rebuild_xlines.py FILE [OUT]`, `plan_reach_audit.py FILE [MAX]` | Restyle my tagged dims to a new sample; recreate Xlines from my tagged dims; audit the 1 m reach. | ACTIVE |
| `plan_rows.py FILE --box X0 Y0 X1 Y1 [--dry] [--replace] [--expect MTIME]` | Mode B generator (fewest lines by ILP, `place_texts`, tagged CLAUDE_ROWS); also the LIBRARY of plan_xlines / plan_clouds. | ACTIVE |
| `plan_sizes.py FILE --box X0 X1 Y0 Y1` | Field-engineer size pass: every element's own size as an item. | ACTIVE |
| `plan_audit.py`, `plan_crossings.py [--tol 12.5]`, `plan_overlaps.py` | Audits: face coverage, the user's line rules, text overlaps (X / Y only). | ACTIVE (inspectors) |
| `scripts/block_reader.py FILE [--box ..] [--name N]` | Classifies every INSERT (element_group / nested / symbol / annotation); `expand_groups` / `restore_groups`. | ACTIVE |
| `plan_elements.py`, `plan_continuity.py`, `plan_chains.py` | First-generation site-plan toolkit (pier chains, blocks, continuity, wall-text shift). plan_rows / plan_xlines / plan_clouds import them. | LIB |
| `plan_lines.py`, `plan_gallery.py`, `plan_tidy.py`, `plan_review.py`, `plan_revise.py` | Earlier generators (full-width greedy lines, gallery chains, tidy / review / revise by cloud colour). plan_tidy / plan_revise are still imported by plan_continuity / plan_review. | SUPERSEDED |

## 6. First-generation section toolkit (ramla ground floor, 2026-10)
| Recipe | Does | Status |
|---|---|---|
| `plan_sections.py FILE --box .. --grid X Y [--shafts]` | A whole floor from scratch: every beam a record, types numbered 1..N, identical sections identified, cut-mark pairs, report. `classify` / `parse_slab` are used by `star_plan`. | LIB |
| `cut_marks.py FILE --num N --view E\|W\|N\|S --at X Y --beam-width B` | Adds a cut-mark pair by copying the user's pair (`ROT, LAYOUT` are used by `star_orient`). | LIB |
| `copy_region.py FILE --box .. --to X Y [--retitle OLD NEW] [--general N]` | Copies a finished drawing (general sections 5 / 6) elsewhere. | ACTIVE |
| `section_outline.py FILE N-N --box X Y W H --beam B H --slab T [--left L] [--right R]`, `dim_section.py FILE N-N [--near X Y] [--full]` | Plain outline + dimensions of a simple L / T section (no rebar). | SUPERSEDED by `ledge_beam` / `general_beam` |
| `scripts/shaft_walls.py`, `scripts/plan_beams.py inventory` | Shaft-wall cut pairs; beam inventory with fallbacks. | ACTIVE (first-gen floors) |
| `legacy/rebar_section.py`, `legacy/rebar_notes.py` | Rebar geometry / notes of 1-1..5-5 from 76-76 (`--check76`). | LEGACY |

## 7. Inspectors and learning (scripts/)
`dxf_inspect.py FILE <cmd>` (summary, find, near X Y R, png X0 X1 Y0 Y1 OUT, layers, dims, dimstyles, blocks, entity HANDLE, audit, diff, layouts, **markup**); `learn_diff.py USER SNAPSHOT --box X0 Y0 X1 Y1 [--auto-shift]` (what he added / removed / changed); `plan_layers.py FILE --box .. -o OUT.txt` + `layer_roles.py` (layer inventory + role guesses); `dxflib.py` (load_profile, decode / encode, describe, render_png, diff, backup, levels, in_box, stirrup_layout / stirrup_extend, mid_steel, **ensure_standards / ensure_section_standards** (import missing layers / dim styles / blocks from `assets/office_standards.dxf`; rebuild with `build_office_assets.py`), step_groups, blue_clouds, target_cells). The DimPlan app lives in `Desktop\AI\constructionPlan` (supersedes the old `dim_app` / `DimPlanApp`); rebuild it (`python build.py`) after skill changes.

## Writing a new recipe
1. Show the rule list you extracted from the reference; get a nod if it is unusual. 2. Constants on top (layers, styles, offsets, tolerances) with a comment where each came from - or in the profile. 3. Locate the element relative to an anchor (title text, block), never absolute coordinates. 4. `--dry` prints the plan; the real run snapshots, updates the original in place and can render a PNG; a second run must change nothing. 5. Add the row above, a CHANGELOG line, a test, and the convention in `conventions/`.
