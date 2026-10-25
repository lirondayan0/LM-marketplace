"""Recipe: roller-shutter downstand UNDER a general beam that has slab on both sides (user's hand edit of korchakk 6-6, 2026-10-24; 1 example, UNVERIFIED beyond it).
  python beam_shutter.py FILE --face-x X --beam-bottom Y --slab-top Y --soffit Y --b 10 --h 35 [--side right] [--h-dim-x X] [-o OUT] [--dry]
The downstand b x h hangs from the BEAM bottom, flush with the stem face at --face-x (--side right = the downstand extends to the right of that face, left = to the left).
Rules (conventions/sections-drawing.md): outline 3 lines on 9_KONTUR and the beam-bottom line under it removed; closing bar 3 from the outer face from shutter bottom+3 up to soffit+10.3;
ONE column of dots at the shutter centre (array + help line); `2$10` shelf runs AWAY from the stem, 12 beyond the shutter; dims b under (18.6 below the bottom), the beam-width dim moves
below it (32.6 below the bottom); height dim at --h-dim-x (his slab-end column, under the slab D dim); L stirrup outside on the left, NUMERIC (40 leg, vertical = slab top-3 .. shutter bottom+3);
OUTSIDE (חוץ) / INSIDE (פנים) boxes flank the shutter at its bottom (user's hand edit of netivot 9-9, 2026-10-25: he added them; the first example had none - newest wins). Does not add the o.k. marker (ok_marker.py)."""
import argparse, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ezdxf
import ledge_beam as LB
import slab_edge as SE

def draw(doc, fx, yb, ytop, ysoff, b, h, side, hdx, stirrup_dx=93.0, leg=40.0):      # stirrup_dx 100.6 -> 93.0: his netivot 9-9 moved the whole stirrup detail 7.6 closer
    msp = doc.modelspace(); Ly = LB.PROF['layers']; Dm = LB.PROF['dim']; z = '56_HATAH_ZET'; s = 1 if side == 'right' else -1
    xa, xb = fx, fx + s * b                                              # outer face (stem face) / inner face of the downstand
    X = lambda u: fx + s * u
    ol = Ly['outline_new']
    for a, c in (((fx, yb), (fx, yb - h)), ((fx, yb - h), (xb, yb - h)), ((xb, yb - h), (xb, yb))): msp.add_line((a[0], a[1]), (c[0], c[1]), dxfattribs=dict(layer=ol))
    for e in msp.query('LINE[layer=="%s"]' % ol):                          # the beam-bottom line must not run across the shutter mouth
        if abs(e.dxf.start.y - yb) < .2 and abs(e.dxf.end.y - yb) < .2 and min(e.dxf.start.x, e.dxf.end.x) <= min(fx, xb) + .2 and max(e.dxf.start.x, e.dxf.end.x) >= max(fx, xb) - .2:
            lo, hi = sorted((e.dxf.start.x, e.dxf.end.x)); e.dxf.start = (max(fx, xb), yb, 0) if s == 1 else (lo, yb, 0); e.dxf.end = (hi, yb, 0) if s == 1 else (min(fx, xb), yb, 0); break
    bar_x = X(3.0); msp.add_lwpolyline([(bar_x, ysoff + 10.3), (bar_x, yb - h + 3.0)], dxfattribs=dict(layer='57_HATAH_ZIUN'))
    cx = X(b / 2.0); v_top, v_bot = yb - 5.0, yb - h + 5.2; n = max(2, int(-(-(v_top - v_bot) // 20)) + 1); vs = [v_top + (v_bot - v_top) * k / (n - 1) for k in range(n)]
    for v in vs:
        if SE.DOT_BLOCK in doc.blocks: msp.add_blockref(SE.DOT_BLOCK, (cx, v), dxfattribs=dict(layer=SE.DOT_LAYER, rotation=180.0, xscale=-SE.DOT_SCALE, yscale=SE.DOT_SCALE))
        else: LB.add_dot(msp, cx, v, '57_HATAH_ZIUN')
    msp.add_line((cx, vs[0]), (cx, vs[-1]), dxfattribs=dict(layer='2000_DOT_HELP_LINE'))
    ex, ey = xb + s * 12.0, yb - h + 1.0       # note elbow: 12 beyond the inner face, i.e. AWAY from the stem
    for tip in ((cx, vs[-1]), (cx - s * 1.5, vs[-1] + 6.4)): msp.add_line(tip, (ex, ey), dxfattribs=dict(layer=z))
    msp.add_lwpolyline([(ex, ey), (ex + s * 24.2, ey)], dxfattribs=dict(layer=z))
    msp.add_text('2$10', height=6.0, dxfattribs=dict(layer='54_HATAH_TEXT', style='HEBREW_NEW', width=0.8, insert=(ex + s * 3.1, ey + 1.4)))
    def dim(**k): msp.add_linear_dim(dimstyle=Dm['style'], override=Dm['override'], dxfattribs={'layer': Ly['dim']}, **k).render()
    dim(base=(xb, yb - h - 18.6), p1=(fx, yb - h), p2=(xb, yb - h), angle=0)
    dim(base=(hdx + 0.4, yb), p1=(hdx - 29.6, yb - h), p2=(hdx - 29.6, yb), angle=90)      # his 9-9: the height dim joins the existing right-hand chain (65 / 25 / 10: dimension line at slab end + 76.8), not a column of its own 30 further right
    # L stirrup, outside on the left, numeric
    top = ytop - SE.BAR_COVER; bot = yb - h + SE.BAR_COVER; u0 = fx - stirrup_dx; u1 = u0 - leg; hv = top - bot
    n0 = len(msp)
    leg_ = msp.add_lwpolyline([(u0, top), (u1, top), (u1, bot)], dxfattribs=dict(layer='57_HATAH_ZIUN'))
    for base, p1, p2, ang, loc in (((u1, top), (u0, top), (u1, top), 0, ((u0 + u1) / 2.0, top + 6.0)), ((u1, top), (u1, top), (u1, bot), 90, (u1 - 6.0, (top + bot) / 2.0))):      # his 9-9: the 40 text ABOVE its line, the 64 text LEFT of the leg (the note is on the right): explicit text positions, not the style's guess
        msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=ang, location=loc, dimstyle=SE.BARZEL_ABOVE, dxfattribs={'layer': Ly['dim']}).render()
    L = int(math.ceil((leg + hv) / 5.0) * 5)
    msp.add_text('$8@15 L=%d' % L, height=6.0, dxfattribs=dict(layer='54_HATAH_TEXT', style='HEBTXT', width=0.8, rotation=90.0, insert=(u1 + 10.0, bot + 8.2)))      # his 9-9: the note sits 10 RIGHT of the leg (the dim 64 is ON the leg, its text on the left): they no longer overlap, so no pass pushes them 30 left
    # OUTSIDE / INSIDE boxes (his 9-9): 28.4 x 13 on ONE line at the shutter bottom (y bottom + 1.4); outside = the stirrup side (left), right edge 20.6 from the shutter's left face; inside = 46.0 right of its right face
    lo, hi = min(fx, xb), max(fx, xb)
    for bx0, raw, tu, tv in ((lo - 20.6 - 28.4, 'ju.', 22.0, 3.2), (hi + 46.0, 'pbho', 22.8, 2.7)):
        by0 = yb - h + 1.4
        msp.add_lwpolyline([(bx0, by0), (bx0 + 28.4, by0), (bx0 + 28.4, by0 + 13.0), (bx0, by0 + 13.0)], close=True, dxfattribs=dict(layer='55_HATAH_TEXT'))
        msp.add_text(raw, height=6.0, dxfattribs=dict(layer='55_HATAH_TEXT', style='SIVAN', width=0.8, text_generation_flag=2, insert=(bx0 + tu, by0 + tv)))
    if 'DXFSKILL_GROUP' not in doc.appids: doc.appids.add('DXFSKILL_GROUP')
    for e_ in [leg_] + [x for x in list(msp)[n0:] if x is not leg_ and (x.dxftype() == 'DIMENSION' or (x.dxftype() == 'TEXT' and x.dxf.text.startswith('$8@15')))]:
        e_.set_xdata('DXFSKILL_GROUP', [(1000, 'stirrup-detail %.1f' % fx)])      # the detail (leg, its 2 dims, the note) is ONE object for fit_rows: it may straddle the cell divider, the pieces must move together
    return dict(n_dots=n, L=L, stirrup_v=round(hv, 1))

def move_width_dim(doc, fx, yb, h, stem_w):
    """the beam-width dim (def point on the stem, under the beam) is recreated 32.6 below the shutter bottom"""
    msp = doc.modelspace()
    for e in list(msp.query('DIMENSION')):
        if abs(e.dxf.defpoint3.x - e.dxf.defpoint2.x - stem_w) < .3 and abs(e.dxf.defpoint2.y - yb) < .3 and abs(e.dxf.get('angle', 0)) < .1 and e.dxf.defpoint.y < yb - 1:
            sty, lay, g = e.dxf.dimstyle, e.dxf.layer, e.dxf.geometry; p1, p2 = e.dxf.defpoint2, e.dxf.defpoint3
            msp.delete_entity(e); doc.blocks.delete_block(g, safe=False)
            msp.add_linear_dim(base=(p1.x, yb - h - 32.6), p1=(p1.x, p1.y), p2=(p2.x, p2.y), angle=0, dimstyle=sty, dxfattribs={'layer': lay}).render(); return True
    return False

def main():
    a = argparse.ArgumentParser(); a.add_argument('file'); a.add_argument('--profile', default='israeli-structural')
    a.add_argument('--face-x', type=float, required=True); a.add_argument('--beam-bottom', type=float, required=True); a.add_argument('--slab-top', type=float, required=True); a.add_argument('--soffit', type=float, required=True)
    a.add_argument('--b', type=float, required=True); a.add_argument('--h', type=float, required=True); a.add_argument('--side', choices=('left', 'right'), default='right')
    a.add_argument('--h-dim-x', type=float, required=True, help='x of the slab-end column where the height dim goes (under the slab D dim)'); a.add_argument('--stem-w', type=float, default=20.0)
    a.add_argument('-o'); a.add_argument('--dry', action='store_true'); a = a.parse_args(); LB.apply_profile(a.profile)
    doc = ezdxf.readfile(a.file)
    info = draw(doc, a.face_x, a.beam_bottom, a.slab_top, a.soffit, a.b, a.h, a.side, a.h_dim_x); info['width_dim_moved'] = move_width_dim(doc, a.face_x, a.beam_bottom, a.h, a.stem_w); print(info)
    if a.dry: return
    out = a.o or a.file
    if out == a.file: LB.backup(a.file, 'beamshutter')
    doc.saveas(out); print('saved', out, '| audit errors', len(ezdxf.readfile(out).audit().errors))

if __name__ == '__main__': main()
