# Office standards (Israeli structural office; user = civil/structural engineer) - shared by section and plan work
CURRENT rules only; evidence trail and superseded versions: not kept in the skill (archive copy: `~/.claude/skill-backups/dxf-drafting-history-archive-20261024`). Constants live in `../profiles/israeli-structural.json`. Confidence: V = verified on 2+ cases or user-confirmed, 1 = one example, ? = my inference (UNVERIFIED).

## Files, units, scale
- Units **cm** (`$INSUNITS` may say mm: trust the geometry - a 20 wall measures 20). DXF AC1032, drawing in model space. DWG cannot be read: ask for DXF. V
- Sections plot 1:25 (text 6, arrows 1, style `dim_25`); plans 1:50 (`dim_50`, text 12) or 1:100 (`dim_100`, text 24). V
- Section sheets: white target cells on `72_MISGERET_WIN` (see sections-workflow.md). The user's comments: layer `claude` (markup-vocabulary.md).

## Hebrew text and symbols
- Hebrew is stored as ENGLISH-KEYBOARD characters in SHX styles (`SIVAN`, `HEBTXT`, `MIRYL`, `HEBREW_NEW`); read with `dxflib.decode`, write with `encode`, only for SHX styles (TTF styles take Unicode). `%%U` = underline. Examples: `j,l` = חתך, `pbho` = פנים, `ju.` = חוץ, `kph ,fbh,` = לפי תכנית, `c/g/` = ב.ע., `c/,/` = ב.ת.
- Mirrored (RTL) notes copy the reference text's `text_generation_flag` (2) and run LEFT from their insert point (ezdxf bbox is wrong for them: measure with `scripts/shx_width.py`). Never centre a title from its bbox.
- Plan texts are stored REVERSED, digits included (raw `08=D` = D=80): parse both `D=nn` and `nn=D`. Decode only texts that contain lowercase letters (a layer like `451TEXT_KORA_100` also holds plain `200/100`).
- Bar notes: `$` = Ø (`4$12`, `2$8@20`, `$12@15 L=..`). Older ground-floor examples use `&`. EVERY note that contains `$` is style **HEBREW_NEW** (HEBTXT shows a wrong glyph; `sivan_text.py` enforces it). Other Hebrew section notes are SIVAN (width 0.7, mirrored, standing on the shelf); MIRYL for ` zhui kph ,fbh,` (reinforcement per plan).
- Section title `%%Uחתך N-N`: SIVAN h9, width 0.9, mirrored; `1:25` HEBREW_NEW h6 w0.8; both on `54_HATAH_TEXT`. **Two-digit numbers are written digit-reversed** (10 -> `01-01`, 12 -> `21-21`; 11, 22 unchanged); the plan marks (hat attributes) keep plain digits. V
- Windows console garbles Hebrew: write reports to a UTF-8 file and read that.

## Layers of a section (names are transliterated Hebrew: HATAH=חתך, MIDA=מידה, ZIUN=ציון, ZET=leader, KIR=קיר, KORA=קורה, BARZEL=ברזל; full office list = skill `anthropic-skills:construction-layers`)
| Element | Layer | Colour (user's table, 2026-10-21; entities stay BYLAYER) |
|---|---|---|
| Outline (new cast / existing) | `9_KONTUR` / `5_HATAH _KONTUR` (note the space) | 3 / 3 |
| Dimensions | `53_HATAH_MIDA` (detail dims on `54_HATAH_TEXT`) | 2 |
| Text, titles | `54_HATAH_TEXT` | 3 |
| Leaders | `56_HATAH_ZET` | 6 |
| Rebar: dots, stirrups, bar lines, mesh, level marker block | `57_HATAH_ZIUN` | **4 (light blue; pure ACI 5 was rejected)** |
| Help lines | `2000_DOT_HELP_LINE` | - |
| Panel dashes | `51_HATAH_DASHED` (`57_HATAH_DASHED` for a wall above) | - |
| Bar-end dot block `dot barzel` | `1922_ZIUN_DOT_T+I` | - |
| Hollow-core voids (obrounds) | `10_PLADA_HATAH` | **3 (green)** - a recipe that creates a layer must set the office colour (default is 7); the plan's own `10_PLADA_HATAH` arrived white (7) in shlang and the user recoloured it by hand - `ledge_beam.obround` now forces 3 |
| Target cells | `72_MISGERET_WIN` | 7 |
`rebar_color.py` applies this table (layer colours, clears overrides). The level marker is the user's block `o.k block` (inside: `MH` arrow + `o.k` + mirrored 'לפי תכנית'; assets/o_k_block.dxf) on `57_HATAH_ZIUN`; the layer `58_HATAH_SIM` appeared only in the first example.

## Dimension styles
- Sections: `dim_25` with per-dim override `dimexo=1.5, dimexe=2.0` (the style's dimexo=40 hides extension lines); measured text, never a text override. Bar shapes: `dim_25_BARZEL` (text only, written ON the bar; vertical legs `25_BARZEL_Below` family). Vertical section dims: text centre 4.5 outside the line (`location=`, lower point first).
- Plans: layer `36_MIDA_CLALI`, style `dim_50` / `dim_100` (the user's sample dimension decides, see plan-dimensions.md).

## Plan vocabulary (details: knowledge/structural-plan-reading.md)
- Beam tag `b/h` (cm; h includes the slab) on `451TEXT_KORA_100` / `45_TEXT_KORA`; levels `o.k.` / `u.k.` (top / soffit), slab block `S_M` (attribs `D=nn`, level) and text `D=a+b`: **hollow-core panel a + cast topping b - ground floor 25+7, mezzanine/gallery 20+5**; `D=nn` without `+` = SOLID slab.
- Section cut mark = block `hat` (attribute = number), two per cut; view direction = local +y rotated by the insert rotation (rot 270 E, 180 S, 0 N, 90 W); looking E south is right, S: west right, N: east right, W: north right. V
- **Levels in one datum**: a text may hold two numbers (`-0.30=+4.95`, `o.k.+271.30=+3.80`); compare beam top and slab top after the `=` (absolute). A drop > 150 is a datum mix-up: draw flush and flag.
- Rebar dot = SOLID closed 2-point LWPOLYLINE, bulge 1, const width = bar diameter (1.0 on the Ramla sheet, 1.25 on brenda_karka: never assume one width); the user's own dots are nested anonymous `*U` blocks around `dot barzel`.

## Section indicator layer
- **Rule (user 2026-10-25, red cloud on a numbered `hat` pair in SECTIONS_PLAN.dxf, any DXF)**: every plan section indicator (numbered `hat` cut mark, attribute = section number) lives on layer `23_SIM` (colour 3). On a file received with indicators on another layer run `recipes/section_indicator_layer.py FILE` (`--dry` first). Star marks `S`/`SS`/`ST`/`*` on `automatic_sections` are orders, not indicators: untouched. Evidence: 1 file; reading UNVERIFIED that the cloud meant 23_SIM (the other clouds enclose ST star marks on `automatic_sections`).

## Missing definitions: bring them in (user 2026-10-24: 'if a layer is missing from your plan, know how to bring it in and use it')
- A plan file may lack layers, dim styles, text styles, linetypes or blocks the recipes draw with (shlang had no `dim_25_BARZEL`, a white `10_PLADA_HATAH`, no `dot barzel`). `dxflib.ensure_standards(doc, layers, dimstyles, styles, blocks, linetypes)` imports each missing one from the office standard: layers (colour + linetype) from `assets/office_layers.json` (the 246-layer office list + the recipe layers the list does not name, taken from brenda_karka), the rest from `assets/office_standards.dxf` (tables + blocks copied from his reference drawing). `ensure_section_standards(doc)` = everything the section recipes use; `ledge_beam.template_texts` calls it, so ledge / general / slab_edge runs are covered.
- The plan's own definitions always win (an existing layer is never recoloured; only the void layer is forced green by `obround`). An unknown layer name is created plain (colour 7) with a WARNING; the import list is printed - quote it in the report ('imported from the office standard: ...').
- New layer / style / block needed by a recipe: add its name to `SECTION_*` in dxflib; the office list changed or another reference drawing: rerun `scripts/build_office_assets.py [layers SKILL.md] [reference.dxf]`.
