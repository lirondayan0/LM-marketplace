# ezdxf cookbook (patterns that worked; add yours when you verify one). Docs: ezdxf.mozman.at

Install: `pip install ezdxf matplotlib`. Python on this machine: `python`. Always `sys.stdout.reconfigure(encoding='utf-8')` (dxflib does).

## Read / write
```python
doc = ezdxf.readfile(path); msp = doc.modelspace()      # damaged file: from ezdxf import recover; doc, aud = recover.readfile(path)
shutil.copy2(path, os.path.splitext(path)[0] + '.bak')  # backup first
doc.saveas(path)                                        # update original in place (user's rule)
aud = doc.audit(); aud.errors                           # structural check after writing
```
Save to a scratch file between steps, copy to the final name when done.

## Query / geometry
```python
msp.query('LINE[layer=="5_HATAH _KONTUR"]')             # attribute selectors; also 'TEXT LWPOLYLINE'
from ezdxf import bbox; b = bbox.extents([e]); b.extmin, b.extmax, b.size
e.translate(dx, dy, 0)                                  # move;  e.transform(Matrix44...) for rotate/scale
e.dxf.layer = 'X'; e.dxf.color = 256                    # set layer; 256=ByLayer
msp.delete_entity(e)
```
`bbox.extents` on TEXT is approximate (font metrics unknown for SHX).

## Add things
```python
msp.add_line(a, b, dxfattribs={'layer': L})
msp.add_lwpolyline(pts, close=True, dxfattribs={'layer': L})
msp.add_text(txt, height=6, dxfattribs={'layer': L, 'style': S}).set_placement((x, y), align=TextEntityAlignment.MIDDLE_CENTER)
msp.add_mtext(txt, dxfattribs={'layer': L, 'style': S, 'char_height': 6})
blk = msp.add_blockref('MH', (x, y), dxfattribs={'layer': L}); blk.add_auto_attribs({'TAG': 'value'})
h = msp.add_hatch(color=1, dxfattribs={'layer': L}); h.set_pattern_fill('ANSI31', scale=...); h.paths.add_polyline_path(pts)
doc.layers.add('NEW', color=3, linetype='Continuous')   # check existing first: name in doc.layers
```

## Dimensions (verified)
```python
d = msp.add_linear_dim(base=(x, y), p1=(..), p2=(..), angle=0|90, dimstyle='dim_25',
                       override={'dimexo': 1.5, 'dimexe': 2.0}, dxfattribs={'layer': '53_HATAH_MIDA'})
d.render()                                              # REQUIRED: creates the dimension geometry block
```
- `base` = a point the dimension line passes through (so it sets the offset); `angle` 0 = horizontal measurement, 90 = vertical.
- `text='65'` overrides the shown text (avoid: it goes stale when geometry changes; use `<>` for measured).
- Others: `add_aligned_dim`, `add_angular_dim_3p`, `add_radius_dim`, `add_diameter_dim`, `add_arc_dim_3p`. Same `.render()` rule.
- Style-level variables hide things: if extension lines don't show, check `dimexo` > distance and `dimse1/2`.

## Copy conventions from another file
```python
from ezdxf.addons import Importer
imp = Importer(src_doc, dst_doc); imp.import_modelspace(); imp.finalize()       # or imp.import_block('MH'); imp.import_table('layers', ['NAME'])
```
Use to bring layers/styles/blocks (e.g. from `שכבות.dxf`) into a target file; verify the layers exist after.

## Render
`dxflib.render_png(doc, (x0,x1,y0,y1), out)` — matplotlib backend. SHX Hebrew shows as mirrored Latin gibberish; that is the renderer, not the file. Warning "Ignoring fixed y limits…" is harmless. Render a small region (≈ element ± margin) so details are legible.

## Windows shell
`python - <<'EOF'` heredocs break when the code contains quote characters and Hebrew in Git Bash; write scripts with the Write tool into the scratchpad and run them. Hebrew file names work fine when passed as arguments.

## Dimensions on bars (rebar shapes), 2026-10-06
- Text-only dimension = a dimstyle with dimsd1/dimsd2/dimse1/dimse2 = 1 and dimblk `_None` (office style `dim_25_BARZEL`). `msp.add_aligned_dim(p1, p2, distance=0, dimstyle=...)` puts the line ON the bar; the text is on the left of p1->p2, so swap the points to change the side.
- A 'plain' dimension whose points sit on the dimension line: `add_linear_dim(base=(x, y), p1=(x0, y), p2=(x1, y), angle=0)` (no extension lines).
- Solid rebar dot = closed 2-point LWPOLYLINE with bulge 1 and `const_width` = diameter (width 0 draws a hollow ring). Dots in the user's files live in nested anonymous blocks (`*U..`): flatten with `virtual_entities()` recursively to read them.
- Reading `dimtype`: 32 = block-exclusive flag; 33 aligned, 161 aligned with moved text, 0/32 linear. A dim's rendered text is in its geometry block (`virtual_entities()`).
- Deleting a dimension: also delete its anonymous geometry block (`doc.blocks.delete_block(name, safe=False)`).
