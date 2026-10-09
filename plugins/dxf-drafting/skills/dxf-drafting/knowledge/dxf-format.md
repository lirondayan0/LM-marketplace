# DXF format facts (universal; keep office-specific rules in `conventions/`)

## Structure
Sections in order: HEADER (variables `$INSUNITS`, `$DIMSCALE`, `$LTSCALE`...), CLASSES, TABLES (LAYER, LTYPE, STYLE=text styles, DIMSTYLE, BLOCK_RECORD, VPORT, APPID), BLOCKS (block definitions incl. anonymous `*D…` dimension geometry, `*U…`, `*Model_Space`, `*Paper_Space…`), ENTITIES (model space), OBJECTS (dictionaries, layouts, MLEADERSTYLE, groups). Every object has a unique hex **handle**; `entity HANDLE` in the inspector dumps one.
Text DXF is group-code/value pairs; binary DXF exists (ezdxf reads both). Versions: AC1015=R2000, AC1018=R2004, AC1021=R2007, AC1024=R2010, AC1027=R2013, AC1032=R2018+. DWG is a different, proprietary format: not readable, ask for DXF export.

## Units and scale
- `$INSUNITS`: 0 unitless, 1 in, 2 ft, 4 mm, 5 cm, 6 m. Drawings are drawn **1:1 in real units**; scale only matters for plotting: text height, arrow size, dimension offsets are set so that (drawing units × plot scale) = paper size. At 1:25 in cm, text 6 cm ⇒ 2.4 mm on paper.
- `$DIMSCALE` (global) or per-dimstyle `dimscale` multiplies dimension sizes; `dimscale=0` in a dimstyle means "use paperspace viewport scale". `$LTSCALE` scales linetype patterns.
- Measured dimension text = real length × `dimlfac`; check `dimdec` (decimals), `dimzin` (zero suppression) before trusting displayed numbers.

## Spaces and layouts
Model space = the real drawing. Paper space layouts hold viewports (scale = viewport height / model view height) and title blocks. Many engineering files are model-only with a scale by convention.

## Entities worth knowing
LINE, LWPOLYLINE (2D, bulge arcs, closable, `const_width`), POLYLINE (legacy 2D/3D), ARC, CIRCLE, ELLIPSE, SPLINE, TEXT (single line, `style`, `height`, `rotation`, `halign/valign` + `align_point`), MTEXT (formatted; `\P` newline; `{\fFont|...;text}`), INSERT (block reference with ATTRIBs), HATCH (boundary paths + pattern/solid), DIMENSION (linear/aligned/angular/radius/diameter/ordinate; subtype in `dimtype`), LEADER (legacy), MULTILEADER (modern), VIEWPORT, IMAGE/XREF (external; avoid breaking the path), POINT, SOLID, 3DFACE, MESH, ATTDEF (block attribute template).
Important: a **DIMENSION is an entity plus an anonymous block** holding its drawn geometry. Programmatically created dims must be `.render()`ed so the block exists; AutoCAD re-generates the block when the dim is edited/updated.

## Layers, styles, appearance
- Layer = name, ACI color (1–255; 256 = ByLayer, 0 = ByBlock), linetype, lineweight, on/off, frozen, locked, plot flag. Entities may override color/linetype/lineweight ("not ByLayer") – check before assuming appearance comes from the layer.
- Layer names are case-insensitive in CAD but may contain spaces and `$` (xref-prefixed `X$0$layer`); copy them exactly.
- Dimstyle holds ~80 variables (`dimtxt` text height, `dimasz` arrow, `dimexo` extension offset from origin, `dimexe` extension beyond dim line, `dimgap`, `dimtad` text above line, `dimdec`, `dimblk` arrow block, `dimclrd/e/t` colors, `dimtofl` force line inside, `dimtmove`). An entity can override any of them (stored in XDATA `ACAD`/`DSTYLE`).
- Text style = name → font file (SHX or TTF) + width factor + oblique; font choice determines how bytes are interpreted (see `pitfalls.md` for Hebrew).

## Color
ACI 1 red, 2 yellow, 3 green, 4 cyan, 5 blue, 6 magenta, 7 white/black (contrast), 8/9 greys. True color via `true_color` (24-bit). Dark-background rendering vs paper black: ACI 7 flips.
