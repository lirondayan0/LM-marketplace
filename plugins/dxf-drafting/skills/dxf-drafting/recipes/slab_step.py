"""Recipe: section through the STEP between a thick slab ("transformation slab") and the thinner standard slab, flush on top (user's own 16-16 in korchakk_sections, 70 / 25, 2026-10-24).
  python slab_step.py FILE N-N --origin X Y [--thick 70 --thin 25] [--mirror] [--overlay] [--stamp] [--dry] [-o OUT]
2026-10-25 (the user: 'I want you to learn how to create a stepped section that accounts for varying slab thicknesses'): the drawing is PARAMETRIC. `build` re-creates his 16-16 from rules, every distance
measured from its own anchor in the example: top face (T), the thin soffit (Ts), the thick soffit (S0), the step face (XF). With thick 70 / thin 25 it reproduces the example (test), any other pair keeps the same
anchors (UNVERIFIED beyond 70 / 25, he has drawn one example). `--stamp` = the old exact copy of assets/slab_step_example.dxf (only 70 / 25).
Coordinates below are the example's (cm): origin O = the bottom-row bar dot of the thick slab at the step (y = S0 + 4.64, x = XF - 4.41); thick slab to the LEFT, thin to the right; `--mirror` reflects x about the step face.
--overlay (XREF): only reinforcement, notes and the U-bar detail (the XREF draws outline, break marks and the three slab dims).
Rules (conventions/sections-drawing.md 'Slab step'): thick side top + bottom rows of dots (pitch 15.1) with a U bar [ (3 from the faces), top bar through; thin side bottom bar from 53 inside the thick slab, dot rows at 15; thick > 30:
two tie dots on the step face with `&12@20` (one when the step face is shorter than 40); per-plan notes top / bottom / thin side; `o.k.` marker on the top face; U-bar detail below (legs 80, vertical = thick - 6, lap dims,
two up-arrow leaders into the section's bars)."""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ezdxf
from ezdxf.addons.importer import Importer
from ezdxf.math import Matrix44
import ledge_beam as LB

ASSET = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'slab_step_example.dxf')
EXAMPLE_THICK, EXAMPLE_THIN = 70.0, 25.0
XL, XR, XF, S0 = -79.3, 95.5, 4.41, -4.64          # left end, right end, step face, thick soffit (example)
ROW_PITCH, THIN_X0, THIN_PITCH = 15.08, 9.1, 15.0    # thick-side dot pitch / first thin-side dot / thin-side pitch
TIE_MIN_STEP = 40.0                                 # step face shorter than this: ONE tie dot (UNVERIFIED, the example has 45)


def _import_standards(doc, src):
    """styles / layers / dimstyles + the two blocks the section needs, from the example file (existing ones untouched)"""
    imp = Importer(src, doc); imp.import_tables()
    for b in ('dot barzel', 'mif-hat'):
        if b not in doc.blocks and b in src.blocks: imp.import_block(b)
    imp.finalize()


def build(doc, ox, oy, name, thick=EXAMPLE_THICK, thin=EXAMPLE_THIN, mirror=False, overlay=False):
    """draw the stepped section with its origin (bottom-row bar dot of the thick slab at the step) at (ox, oy); returns (entities added, dims added)"""
    from shx_width import text_extent
    src = ezdxf.readfile(ASSET); _import_standards(doc, src); LB.apply_profile('israeli-structural'); msp = doc.modelspace(); n0 = len(msp)
    T = S0 + thick; Ts = T - thin; step = thick - thin
    Utop = S0 - 75.86; Ubot = Utop - (thick - 6.0); Tbar = Utop + 23.92; Bbar = Ubot - 20.8       # the U-bar detail hangs under the section, its bars 23.9 over / 20.8 under the U
    fx = (lambda x: 2 * XF - x) if mirror else (lambda x: x)
    P = lambda x, y: (ox + fx(x), oy + y)
    line = lambda a, b, lay: msp.add_line(P(*a), P(*b), dxfattribs=dict(layer=lay))
    poly = lambda pts, lay, close=False: msp.add_lwpolyline([P(*p) for p in pts], close=close, dxfattribs=dict(layer=lay))
    def dot(x, y, lay='57_HATAH_ZIUN', rot=0.0, flip=False): msp.add_blockref('dot barzel', P(x, y), dxfattribs=dict(layer=lay, rotation=rot, xscale=-1.0 if flip else 1.0))      # block dots on the rebar layer: bar_arrays turns them into arrays like the polyline dots
    def txt(raw, x, y, style, h=6.0, w=0.8, mirrored=False, rot=0.0, layer='54_HATAH_TEXT', run_left=None):
        """x = the example's insert. A mirrored (reflected) section keeps every text readable: the text keeps its direction, so its insert moves to the other end of the reflected extent"""
        left = mirrored if run_left is None else run_left
        ax = x
        if mirror:
            try: x0, x1 = text_extent(style, raw, x, h, w, mirrored)
            except Exception: x0, x1 = (x - 0.62 * h * w * len(raw), x) if mirrored else (x, x + 0.62 * h * w * len(raw))      # no SHX table for this style (Standard): approximate
            lo, hi = min(x0, x1), max(x0, x1); ax = (2 * XF - lo) if left else (2 * XF - hi)
        a = dict(layer=layer, style=style, width=w, insert=(ox + (ax if mirror else x), oy + y)); a.update(text_generation_flag=2) if mirrored else None; a.update(rotation=rot) if rot else None
        return msp.add_text(raw, height=h, dxfattribs=a)
    def leader(pts, dimstyle, lay='56_HATAH_ZET'): return msp.add_leader([P(*p) for p in pts], dimstyle=dimstyle, dxfattribs=dict(layer=lay))
    xs_thick = []; k = 0
    while -ROW_PITCH * k >= XL + 3.9 - 0.05: xs_thick.append(-ROW_PITCH * k); k += 1
    xs_thin = []; k = 0
    while THIN_X0 + THIN_PITCH * k <= XR - 8.0: xs_thin.append(THIN_X0 + THIN_PITCH * k); k += 1
    ytop_dot, ybot_dot = T - 4.37, S0 + 4.64
    # --- outline, break marks, title (the XREF carries them) ---
    if not overlay:
        line((XL, T), (XR - 0.1, T), '5_HATAH _KONTUR')
        poly([(XL, S0), (XF, S0), (XF, Ts), (XR + 0.1, Ts)], '5_HATAH _KONTUR')
        zl = T - 21.8; poly([(XL, T + 7.5), (XL, zl + 1.9), (XL - 5.2, zl), (XL + 5.0, zl), (XL, zl - 1.7), (XL, S0 - 6.7)], '5_HATAH _KONTUR')
        zr = T - 10.0; poly([(XR + 0.1, T + 7.0), (XR + 0.1, zr + 1.8), (XR - 5.2, zr), (XR + 5.1, zr), (XR + 0.1, zr - 1.8), (XR + 0.1, Ts - 23.9)], '5_HATAH _KONTUR')
        mh = msp.add_blockref('mif-hat', P(19.0, T), dxfattribs=dict(layer='23_SIM', xscale=-0.5 if not mirror else 0.5, yscale=0.5))
        mh.add_attrib('LEVEL', 'o.k.=', insert=P(21.66, T + 16.75), dxfattribs=dict(height=6.0, style='HEBREW', width=0.8, layer='23_SIM'))      # the attribute stands over the arrow, as in his 16-16
        txt(' kph ,fbh,', 61.9, T + 7.4, 'MIRYL', 6.0, 0.876)
        TT = LB.PROF['title']; txt(TT['prefix'] + LB.title_name(name), 38.8, T + 56.8, TT['style'], TT['height'], TT['width'], mirrored=True); st_ = TT['scale_text']; txt(st_['text'], 6.2, T + 45.1, st_['style'], st_['height'], st_['width'])      # the profile's scale text (his example used Standard, which center_titles cannot measure)
    # --- bars: top bar through, thick-side U bar, thin bottom bar ---
    poly([(XL, T - 3.0), (XR - 0.1, T - 3.0)], '57_HATAH_ZIUN')
    for a, b in (((XL, S0 + 3.24), (XF - 3.0, S0 + 3.24)), ((XF - 3.0, S0 + 3.24), (XF - 3.0, T - 3.0)), ((XF - 3.0, T - 3.0), (XL, T - 3.0))): line(a, b, '57_HATAH_ZIUN')
    poly([(XF - 53.0, Ts + 3.0), (XR - 0.1, Ts + 3.0)], '57_HATAH_ZIUN')
    for x in xs_thick: dot(x, ybot_dot, rot=180.0, flip=True); dot(x, ytop_dot)
    for x in xs_thin: dot(x, T - 4.2, rot=180.0, flip=True); dot(x, Ts + 3.8, rot=180.0, flip=True)      # his example keeps them on 1931_ZIUN_DOT inside arrays; here the rebar layer, so they are arrays + blue like every bar
    # --- step face ties (thick > 30: &12@20) ---
    if thick > 30:
        if step >= TIE_MIN_STEP: ty = [Ts - 11.3, Ts - 26.3]
        else: ty = [(S0 + Ts) / 2]
        for y in ty: dot(-0.1, y)
        ey = ty[-1] - 5.2 if len(ty) == 1 else Ts - 31.5
        poly([(-0.1, ty[-1]), (14.5, ey), (-0.1, ty[0])] if len(ty) == 2 else [(-0.1, ty[0]), (14.5, ey)], '56_HATAH_ZET')
        line((45.4, ey), (14.5, ey), '56_HATAH_ZET'); txt('&12@20', 17.0, ey + 2.0, 'HEBTXT', 6.0, 0.8)
    # --- notes per plan: top, bottom, thin side ---
    xtop = [xs_thick[3], xs_thick[4]]; xbot = [xs_thick[2], xs_thick[1]]
    for x in xtop: line((x, ytop_dot), (-25.3, T + 23.4), '56_HATAH_ZET')
    poly([(-25.3, T + 23.4), (37.3, T + 23.4)], '56_HATAH_ZET'); txt("c/g/ kph ,fbh,", 34.1, T + 25.7, 'MIRYL', 6.0, 0.876)
    for x in xbot: line((x, ybot_dot), (13.1, -27.7), '56_HATAH_ZET')
    poly([(75.7, -27.7), (13.1, -27.7)], '56_HATAH_ZET'); txt("c/,/ kph ,fbh,", 72.2, -25.3, 'MIRYL', 6.0, 0.876)
    xn = xs_thin[4]; line((121.1, T + 17.2), (80.6, T + 17.2), '56_HATAH_ZET'); line((xn, T - 4.2), (80.6, T + 17.2), '56_HATAH_ZET'); poly([(xn, Ts + 3.8), (80.6, T + 17.2)], '56_HATAH_ZET'); txt(' kph ,fbh,', 124.1, T + 19.0, 'MIRYL', 6.0, 0.876)
    # --- U-bar detail under the section ---
    poly([(XL, Ubot), (XF - 3.0, Ubot), (XF - 3.0, Utop), (XL, Utop)], '57_HATAH_ZIUN')
    txt("euyr upxhgv gwwp", -4.3, Ubot + 3.8, 'MIRYL', 6.0, 0.9)
    poly([(XF - 53.0, Tbar), (XR - 0.1, Tbar)], '57_HATAH_ZIUN'); poly([(XF - 53.0, Bbar), (XR - 0.1, Bbar)], '57_HATAH_ZIUN')
    for yb in (Tbar, Bbar):                          # bar-end wave (two arcs, bulge +-0.575)
        w = msp.add_lwpolyline([(P(XR - 0.1, yb + 5.6)[0], oy + yb + 5.6, 0, 0, 0.577 * (-1 if mirror else 1)), (P(XR - 0.1, yb)[0], oy + yb, 0, 0, -0.574 * (-1 if mirror else 1)), (P(XR - 0.1, yb - 5.6)[0], oy + yb - 5.6, 0, 0, 0)], format='xyseb', dxfattribs=dict(layer='HATAH_ZIUN_17'))
    txt('c/g rmpv', 46.3, Tbar - 8.5, 'MIRYL', 6.0, 0.8, run_left=False); txt('c/, rmpv', 46.3, Bbar - 8.5, 'MIRYL', 6.0, 0.8, run_left=False)
    for yb in (Tbar, Bbar): txt('$', -13.6, yb - 5.3, 'HEBREW_NEW', 6.0, 0.8, rot=180.0)
    leader([(-56.3, S0 + 3.24), (-56.3, Ubot)], 'dim_50_BARZEL'); dot(-56.3, Ubot, lay='56_HATAH_ZET', rot=-90.0)
    leader([(-25.9, Ts + 2.9), (-25.9, Bbar - 0.2)], 'dim_50_BARZEL'); dot(-25.9, Bbar - 0.2, lay='56_HATAH_ZET', rot=-90.0)
    txt('zhui ceunv', -6.2, Ubot - 8.0, 'SIVAN', 6.0, 0.7, mirrored=True, layer='411_TEXT_100')
    leader([(-25.1, Bbar - 13.8), (-13.1, Bbar - 33.4), (20.2, Bbar - 33.4)], 'dim_25')
    t = txt('jphv', 13.2, Bbar - 30.6, 'SIVAN18', 6.0, 0.8, mirrored=True)
    # --- dims ---
    nd = 0
    def dim(base, p1, p2, ang, style, text=None, lay='53_HATAH_MIDA'):
        nonlocal nd
        kw = dict(text=text) if text else {}
        msp.add_linear_dim(base=P(*base), p1=P(*p1), p2=P(*p2), angle=ang, dimstyle=style, dxfattribs={'layer': lay}, **kw).render(); nd += 1
    if not overlay:
        dim((113.1, Ts), (XF - 0.02, S0), (XR + 0.05, Ts), 90.0, 'dim_25'); dim((113.1, T), (XR + 0.05, Ts), (XR + 0.05, T), 90.0, 'dim_25'); dim((-89.84, T), (XL + 0.02, S0), (XL + 0.02, T), 90.0, 'dim_25')
    dim((XF, Bbar - 13.8), (XF - 53.0, Bbar), (XF, Ts), 0.0, 'dim_25', '60'); dim((XF, Tbar - 13.8), (XF - 53.0, Tbar), (XF, T + 83.84), 0.0, 'dim_25', '60')
    dim((XF - 3.02, Utop), (XL + 1.02, Utop), (XF - 3.02, Utop - 11.54), 0.0, 'dim_25_BARZEL_Above', lay='53_HATAH_MIDA')
    dim((XF - 2.99, Utop), (XF - 2.99, Ubot), (XF - 3.02, Utop), 90.0, 'dim_25_BARZEL_Above', lay='53_HATAH_MIDA')
    return len(msp) - n0, nd


def stamp(doc, ox, oy, name):
    """the exact copy of the user's example (70 / 25 only)"""
    src = ezdxf.readfile(ASSET); imp = Importer(src, doc); imp.import_tables(); n0 = {e.dxf.handle for e in doc.modelspace()}
    imp.import_entities([e for e in src.modelspace() if e.dxftype() != 'DIMENSION']); imp.finalize()
    new = [e for e in doc.modelspace() if e.dxf.handle not in n0]; m = Matrix44.translate(ox, oy, 0)
    for e in new: e.transform(m)
    T = LB.PROF['title']
    for e in new:
        if e.dxftype() == 'TEXT' and e.dxf.text.startswith(T['prefix']): e.dxf.text = T['prefix'] + LB.title_name(name)
    msp = doc.modelspace()
    for d in json.load(open(ASSET.rsplit('.', 1)[0] + '.dims.json')):
        kw = dict(text=d['text']) if d['text'] else {}
        msp.add_linear_dim(base=(d['base'][0] + ox, d['base'][1] + oy), p1=(d['p1'][0] + ox, d['p1'][1] + oy), p2=(d['p2'][0] + ox, d['p2'][1] + oy), angle=d['angle'], dimstyle=d['dimstyle'], dxfattribs={'layer': d['layer']}, **kw).render()
    return len(new), len(json.load(open(ASSET.rsplit('.', 1)[0] + '.dims.json')))


def layout(cx, cy, ty=403.0, thick=EXAMPLE_THICK, thin=EXAMPLE_THIN):
    """(ox, oy, extent) for the round's cell at (cx, cy) (400 wide): the section is built into a scratch document, centred horizontally, its title on the row's title line (cell y + ty);
    extent = (xmin, ymin, xmax, ymax, ty) relative to the cell origin"""
    from ezdxf import bbox as BB
    LB.apply_profile('israeli-structural'); sd = ezdxf.new('R2018', setup=True); build(sd, 0.0, 0.0, '1-1', thick, thin)
    xs, ys = [], []
    for e in sd.modelspace():
        if e.dxftype() == 'INSERT': xs += [e.dxf.insert.x - 4, e.dxf.insert.x + 4]; ys += [e.dxf.insert.y - 4, e.dxf.insert.y + 4]; continue
        if e.dxftype() == 'DIMENSION': continue
        b = BB.extents([e])
        if b.has_data: xs += [b.extmin.x, b.extmax.x]; ys += [b.extmin.y, b.extmax.y]
    for e in sd.modelspace().query('DIMENSION'):
        for k in ('defpoint', 'defpoint2', 'defpoint3'): v = e.dxf.get(k); xs.append(v.x); ys.append(v.y)
    T = LB.PROF['title']; tt = next((e.dxf.insert.y for e in sd.modelspace().query('TEXT') if e.dxf.text.startswith(T['prefix'])), None)
    ox = cx + 200 - (min(xs) + max(xs)) / 2; oy = (cy + ty - tt) if tt is not None else cy + 250 - (min(ys) + max(ys)) / 2
    return ox, oy, (min(xs) + ox - cx, min(ys) + oy - cy, max(xs) + ox - cx, max(ys) + oy - cy, ty)


def main():
    a = argparse.ArgumentParser(); a.add_argument('file'); a.add_argument('name'); a.add_argument('--profile', default='israeli-structural'); a.add_argument('--origin', nargs=2, type=float, required=True)
    a.add_argument('--thick', type=float, default=EXAMPLE_THICK); a.add_argument('--thin', type=float, default=EXAMPLE_THIN); a.add_argument('--mirror', action='store_true', help='thick slab on the RIGHT'); a.add_argument('--overlay', action='store_true')
    a.add_argument('--stamp', action='store_true', help='exact copy of the example (70 / 25 only)'); a.add_argument('-o'); a.add_argument('--dry', action='store_true'); a = a.parse_args()
    if a.stamp and (a.thick, a.thin) != (EXAMPLE_THICK, EXAMPLE_THIN): sys.exit('--stamp copies the 70 / 25 example only')
    LB.apply_profile(a.profile); doc = ezdxf.readfile(a.file)
    n, nd = stamp(doc, a.origin[0], a.origin[1], a.name) if a.stamp else build(doc, a.origin[0], a.origin[1], a.name, a.thick, a.thin, a.mirror, a.overlay)
    print('drew %d entities + %d dims at %s (thick %g / thin %g)' % (n, nd, a.origin, a.thick, a.thin))
    if a.dry: return
    out = a.o or a.file
    if out == a.file: LB.backup(a.file, 'slabstep-' + a.name)
    doc.saveas(out); print('saved', out, '| audit errors', len(ezdxf.readfile(out).audit().errors))

if __name__ == '__main__': main()
