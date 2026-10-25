"""Recipe: draw the cut OUTLINE + title of an edge-beam-with-slab section (L shape) in a target box. Usage:
  python section_outline.py FILE.dxf 1-1 --box X0 Y0 W H --beam 30 65 --slab 20 [--left 0] [--right 59] [--dry] [-o OUT] [--png OUT]
Slab(s) on the right (default 59 shown) and/or left of the beam, top flush with the beam top (as ground-floor 1-1 in the examples). Then run dim_section.py (use --near X Y
because the example sheet already has the same section numbers). Rules: ../conventions/sections-drawing.md."""
import argparse, os, shutil, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
from dxflib import *

PROF = load_profile()                 # office constants: ../profiles/*.json (--profile NAME); nothing office-specific is hard-coded below

def build(B, H, T, left, right):
    """Segments + break marks relative to the beam's bottom-left corner. Slab(s) top flush with beam top; left/right = slab length shown (0 = none)."""
    sb = H - T; xl, xr = -left, B + right
    seg = [((xl if left else 0, H), (xr if right else B, H)), ((0, 0), (B, 0))]
    seg += [((xl, sb), (0, sb)), ((0, sb), (0, 0))] if left else [((0, H), (0, 0))]
    seg += [((B, 0), (B, sb)), ((B, sb), (xr, sb))] if right else [((B, 0), (B, H))]
    k = T / 25.0                                        # the zigzag was measured on a 25-thick slab; scale it to T
    zz = [(x, y * k) if i else (x, y) for i, (x, y) in enumerate(PROF['outline']['zigzag_slab25'])] + [(0, -(T + PROF['outline']['zigzag_below_slab']))]
    marks = ([xl] if left else []) + ([xr] if right else [])
    return seg, zz, marks, xl, xr

def main():
    global PROF
    a = argparse.ArgumentParser(); a.add_argument('file'); a.add_argument('name'); a.add_argument('--profile', default='israeli-structural')
    a.add_argument('--box', nargs=4, type=float, required=True, help='X0 Y0 W H of the target cell'); a.add_argument('--beam', nargs=2, type=float, required=True)
    a.add_argument('--slab', type=float, required=True); a.add_argument('--left', type=float, default=0); a.add_argument('--right', type=float)
    a.add_argument('-o'); a.add_argument('--dry', action='store_true'); a.add_argument('--png')
    a = a.parse_args(); PROF = load_profile(a.profile); L, O, T_ = PROF['layers'], PROF['outline'], PROF['title']
    B, H = a.beam; T = a.slab; right = a.right if a.right is not None else O['slab_shown']
    seg, zz, marks, xl, xr = build(B, H, T, a.left, right)
    total = xr - xl; X0 = a.box[0] + (a.box[2] - total) / 2 - xl; Y0 = a.box[1] + O['cell_beam_bottom_y']   # centre the outline in the cell; X0 = beam left face
    doc = ezdxf.readfile(a.file); msp = doc.modelspace(); cxm = X0 + xl + total / 2
    print(f'{a.name}: beam {B:.0f}/{H:.0f}, slab {T:.0f} (left {a.left:.0f}, right {right:.0f}), beam corner ({X0:.0f},{Y0:.0f}), {len(seg)} lines + {len(marks)} break marks + title')
    if a.dry: return
    for p, q in seg: msp.add_line((X0 + p[0], Y0 + p[1]), (X0 + q[0], Y0 + q[1]), dxfattribs=dict(layer=L['outline_new'], ltscale=O['ltscale']))
    for mx in marks:
        sgn = -1 if mx < 0 else 1       # left break mark mirrored so the zigzag points outward
        msp.add_lwpolyline([(X0 + mx + sgn * x, Y0 + H + y) for x, y in zz], dxfattribs=dict(layer=L['break'], linetype='Continuous', ltscale=O['ltscale']))
    for txt, st, h, w, dx, dy in [(T_['prefix'] + a.name, T_['style'], T_['height'], T_['width'], T_['dx_from_centre'], T_['dy_above_top']),
                                  (T_['scale_text']['text'], T_['scale_text']['style'], T_['scale_text']['height'], T_['scale_text']['width'], T_['scale_text']['dx_from_centre'], T_['scale_text']['dy_above_top'])]:
        at = dict(layer=L['text'], style=st, width=w, insert=(cxm + dx, Y0 + H + dy))
        if txt.startswith(T_['prefix']): at['text_generation_flag'] = T_['text_generation_flag']
        msp.add_text(txt, height=h, dxfattribs=at)
    M = PROF['level_marker']
    if M['block'] in doc.blocks:        # level marker 'o.k per plan': tip on the beam top (offset averaged from the user's placements)
        msp.add_blockref(M['block'], (X0 + B / 2 + M['dx_from_beam_centre'] - M['tip_in_block'][0], Y0 + H - M['tip_in_block'][1]), dxfattribs=dict(layer=L['level_marker']))
    out = a.o or a.file
    if out == a.file: backup(a.file, 'outline-' + a.name)
    doc.saveas(out); print('saved', out, '| audit errors', len(ezdxf.readfile(out).audit().errors))
    if a.png: render_png(doc, (X0 + xl - 70, X0 + xr + 70, Y0 - 60, Y0 + H + 100), a.png)
main()
