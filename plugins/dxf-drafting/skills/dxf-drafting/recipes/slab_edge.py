"""Recipe: section through the FREE EDGE of a solid slab with no beam ("ceiling edge", user 2026-10-15). The user drew the CORRECT detail in cell 4 of sections_ramla.dxf (red cloud);
this recipe reproduces it numerically (tests/run_tests.py 'slab_edge').
  python slab_edge.py FILE N-N --box X0 Y0 W H --slab D [--replace] [-o OUT] [--png OUT]
The detail (view N, slab WEST of the edge, free end face on the RIGHT of the view; u, v measured from the end face / the soffit):
- outline (9_KONTUR): top, soffit (58.8 long) and the end face; zigzag break (5_HATAH _KONTUR) at the far end; bar lines 3 from both faces ending 3 short of the edge, joined by a VERTICAL bar at u=-3
  (a U bar closing the edge); 2 rows x 4 `dot barzel` dots (layer 1922_ZIUN_DOT_T+I, scale 0.896, rot 180) at u=-4.5-15k, v=4.3 and D-4.3;
- 'per plan' notes top / bottom with the top leader starting on the 2nd dot from the edge; dim D (dim_25) at u=-75.5; `o.k` marker tip on the top face at u=-11.4;
- the U-bar SHAPE drawn under the section (open polyline 60 x (D-6), closed on the edge side, v=-50.5 .. -36.5) with text-only dims dim_25_BARZEL_Above (60 / 60 / D-6) and the note on layer 411_TEXT_100
  (two SIVAN texts above / below an underline at v=-64.8: 'diameter and spacing per plan' / 'horizontal reinforcement bar').
The section sits in a 400 x 450 cell with the end face at x0+234.4 and the soffit at y0+281.3 (the user's example). Bar diameter / spacing are never given: per plan. --slab-side right draws the mirror image (end face left; star_plan decides the side: the cut end inside claude_Kontur is the slab)."""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ezdxf
import ledge_beam as LB

D_LABEL = None                       # parametric thickness symbol ('H') when the plan gives no D (user 2026-10-18: never guess a thickness)
EDGE_X, SOFFIT_Y = 234.4, 281.3       # end face / soffit inside the 400 x 450 cell (user's example, cell 4 of sections_ramla.dxf)
L_SHOWN, BAR_COVER, EDGE_STOP = 58.8, 3.0, 3.0
DOT_BLOCK, DOT_LAYER, DOT_SCALE, DOT_X0, DOT_STEP, DOT_N, DOT_INSET = 'dot barzel', '1922_ZIUN_DOT_T+I', 0.896, -4.5, 15.0, 4, 4.3
TOP_NOTE = dict(dot=1, elbow=(-21.1, 7.1), ulen=45.3)        # leader from dot k of the top row to the elbow (u, D + 7.1)
BOT_NOTE = dict(start=(-18.9, 4.4), elbow=(-23.0, -15.0), ulen=45.0)
DET_V0, DET_LEN = -50.5, 60.0                                # U-bar shape: bottom edge v, length of the legs
MARK_TIP_U = -11.4
NOTE_LAYER, NOTE_LINE = '411_TEXT_100', (-77.8, -0.7, -64.8)
NOTE_TEXTS = (('euyr upxhgv gwwp', -3.0, -61.7), ('crzk zhui tupeh', -3.5, -73.8))     # raw SIVAN text (user's)
BARZEL_ABOVE = 'dim_25_BARZEL_Above'

def draw(doc, D, ex, ey, tmpl, S=1):
    """S = +1: slab on the LEFT of the view, end face right (the user's detail); S = -1: mirror image (slab on the RIGHT, end face left; texts keep reading direction)."""
    msp = doc.modelspace(); Ly = LB.PROF['layers']; P = lambda p: (ex + S * p[0], ey + p[1]); z = '56_HATAH_ZET'
    line = lambda a, b, lay: msp.add_line(P(a), P(b), dxfattribs=dict(layer=lay))
    poly = lambda pts, lay: msp.add_lwpolyline([P(p) for p in pts], dxfattribs=dict(layer=lay))
    b_, h_ = SHUTTER if SHUTTER else (0.0, 0.0)          # roller-shutter downstand at the free end (user 2026-10-22): b wide, h below the soffit, outer face = the end face
    for a, b in (((-L_SHOWN, D), (0, D)), ((-L_SHOWN, 0), (-b_, 0)), ((0, -h_), (0, D))): line(a, b, Ly['outline_new'])
    if SHUTTER: line((-b_, 0), (-b_, -h_), Ly['outline_new']); line((-b_, -h_), (0, -h_), Ly['outline_new'])
    zig = [(x, y * D / 25.0) if i else (x, y) for i, (x, y) in enumerate(LB.PROF['outline']['zigzag_slab25'])] + [(0, -(D + LB.PROF['outline']['zigzag_below_slab']))]
    poly([(-L_SHOWN - x, D + y) for x, y in zig], Ly['break'])
    for y in (BAR_COVER, D - BAR_COVER): line((-L_SHOWN, y), (-EDGE_STOP, y), '57_HATAH_ZIUN')
    poly([(-EDGE_STOP, D - BAR_COVER), (-EDGE_STOP, BAR_COVER - h_)], '57_HATAH_ZIUN')
    dots = [(DOT_X0 - DOT_STEP * k, y) for y in (D - DOT_INSET, DOT_INSET) for k in range(DOT_N)]
    if DOT_BLOCK in doc.blocks:
        for x, y in dots: msp.add_blockref(DOT_BLOCK, P((x, y)), dxfattribs=dict(layer=DOT_LAYER, rotation=180.0, xscale=-DOT_SCALE, yscale=DOT_SCALE))
    else:
        for x, y in dots: LB.add_dot(msp, *P((x, y)), '57_HATAH_ZIUN')
    def txt(raw, key, x, y):
        a = dict(tmpl[key]); a.update(layer=Ly['text'], insert=P((x, y))); msp.add_text(raw, height=a.pop('height'), dxfattribs=a)
    ex_, ey_ = TOP_NOTE['elbow']; ey_ += D; sx = DOT_X0 - DOT_STEP * TOP_NOTE['dot']
    if S == -1: sx = DOT_X0 - DOT_STEP * (DOT_N - 1); ex_ = sx - 1.6      # mirror: the 'o.k' marker text now runs over the slab (its text lies right of the tip), so the top note starts at the FAR dot, beyond the marker text
    tx_ = (lambda e_, ul: e_ - 1.5) if S == 1 else (lambda e_, ul: e_ - ul + 1.5)      # mirrored: shelf runs to the right of the elbow, the text (right-to-left) stands on it, ending 1.5 short of the shelf end
    line((sx, D - DOT_INSET), (ex_, ey_), z); poly([(ex_, ey_), (ex_ - TOP_NOTE['ulen'], ey_)], z); txt('c/g/ kph ,fw', 'tp_cast', tx_(ex_, TOP_NOTE['ulen']), ey_ + 1.4)
    (sx, sy), (ex_, ey_) = BOT_NOTE['start'], BOT_NOTE['elbow']
    line((sx, sy), (ex_, ey_), z); poly([(ex_, ey_), (ex_ - BOT_NOTE['ulen'], ey_)], z); txt('c/,/ kph ,fw', 'bt_cast', tx_(ex_, BOT_NOTE['ulen']), ey_ + 1.4)
    Dm = LB.PROF['dim']
    kw = dict(text=D_LABEL) if D_LABEL else {}
    msp.add_linear_dim(base=P((-L_SHOWN - 16.7, D)), p1=P((-L_SHOWN, 0)), p2=P((-L_SHOWN, D)), angle=90, dimstyle=Dm['style'], override=Dm['override'], dxfattribs={'layer': Ly['dim']}, **kw).render()
    # U-bar shape under the section: open polyline, closed on the edge side
    v0, v1, ue = DET_V0 - h_, DET_V0 - h_ + (D - 6), -EDGE_STOP + 0.1; us = ue - DET_LEN      # a shutter downstand pushes the U-bar detail and its notes down by h
    poly([(us, v0), (ue, v0), (ue, v1), (us, v1)], '57_HATAH_ZIUN')
    def dm(base, p1, p2, ang): msp.add_linear_dim(base=P(base), p1=P(p1), p2=P(p2), angle=ang, dimstyle=BARZEL_ABOVE, dxfattribs={'layer': Ly['dim']}).render()
    dm((ue, v0), (us, v0), (ue, v0), 0); dm((ue, v1), (us, v1), (ue, v1), 0); dm((ue - 0.1, v1), (ue, v0), (ue, v1), 90)
    a0, a1, ay = NOTE_LINE; ay -= h_; line((a0, ay), (a1, ay), z)
    for raw, x, y in NOTE_TEXTS:
        y -= h_
        xi = x if S == 1 else a0 + a1 - x                        # mirrored shelf = [-a1, -a0]; the text keeps its offset from the (now right) shelf end
        msp.add_text(raw, height=6.0, dxfattribs=dict(layer=NOTE_LAYER, style='SIVAN', width=0.7, text_generation_flag=2, insert=P((xi, y))))
    if SHUTTER: draw_shutter(doc, D, P, b_, h_, S)


SHUTTER = None                       # (b, h) of the roller-shutter downstand from the plan text on layer automatic_Roller_shutter ('10/35' = 10 wide x 35 high; mapping UNVERIFIED)
SH_STIRRUP_LEG, SH_STIRRUP_U = 40.0, 35.0                    # L-shaped closing stirrup of the user's example: 40 horizontal leg into the slab; detail drawn OUTSIDE (right of the end face)


def draw_shutter(doc, D, P, b, h, S):
    """Roller-shutter beam at a free slab edge (user's red clouds, brenda_karka 2026-10-22): downstand b x h at the OUTSIDE end of the slab, 2 bars at its bottom (2$10 leader), the closing stirrup is an L
    (40 leg along the slab top + vertical down the whole downstand = D + h - 6) drawn as a shape to the right with its note `&8@15 L=..`, a `חוץ` (outside) box, dims b (under) and h (right of the end face)."""
    msp = doc.modelspace(); Ly = LB.PROF['layers']; Dm = LB.PROF['dim']; z = '56_HATAH_ZET'; sym = D_LABEL
    # USER CORRECTION 2026-10-22 (brenda_karka 1-1): ONE column of bar dots down the outer face (u=-4.5), evenly spaced from the slab-bottom-bar level (v=4.3) to 5.2 above the downstand bottom
    # (spacing <= 20: 35 -> 3 dots 17.07 apart), with the dashed help line of an associative array (bar_arrays.py turns them into the array); NOT two dots at the bottom
    v_top, v_bot = DOT_INSET, -h + 5.2; n = max(2, int(-(-(v_top - v_bot) // 20)) + 1); vs = [v_top + (v_bot - v_top) * k / (n - 1) for k in range(n)]
    for v in vs:
        if DOT_BLOCK in doc.blocks: msp.add_blockref(DOT_BLOCK, P((DOT_X0, v)), dxfattribs=dict(layer=DOT_LAYER, rotation=180.0, xscale=-DOT_SCALE, yscale=DOT_SCALE))
        else: LB.add_dot(msp, *P((DOT_X0, v)), '57_HATAH_ZIUN')
    msp.add_line(P((DOT_X0, vs[0])), P((DOT_X0, vs[-1])), dxfattribs=dict(layer='2000_DOT_HELP_LINE'))
    ex_, ey_ = -22.0, -h + 1.0                                                   # bar note: shelf at the downstand-bottom level (user: -34 for h=35), 24.2 long, text HEBREW_NEW on it; fork to the two bottom dots
    for tip in ((DOT_X0, vs[-1]), (DOT_X0 + 1.5, vs[-1] + 6.4)): msp.add_line(P(tip), P((ex_, ey_)), dxfattribs=dict(layer=z))      # his fork: bottom dot + a tip 6.4 above it, 1.5 inboard (copied; not on a dot centre)
    msp.add_lwpolyline([P((ex_, ey_)), P((ex_ - 24.2, ey_))], dxfattribs=dict(layer=z))
    msp.add_text('2$10', height=6.0, dxfattribs=dict(layer='54_HATAH_TEXT', style='HEBREW_NEW', width=0.8, insert=P((ex_ - 18.3, ey_ + 1.4))))
    msp.add_linear_dim(base=P((0, -h - 8.0)), p1=P((-b, -h)), p2=P((0, -h)), angle=0, dimstyle=Dm['style'], override=Dm['override'], dxfattribs={'layer': Ly['dim']}).render()
    msp.add_linear_dim(base=P((20.0, 0)), p1=P((0, -h)), p2=P((0, 0)), angle=90, dimstyle=Dm['style'], override=Dm['override'], dxfattribs={'layer': Ly['dim']}).render()
    # L stirrup shape (outside, right of the end face): horizontal leg on the slab-top level, vertical leg = D + h - 6
    top = D - BAR_COVER; hv = D + h - 2 * BAR_COVER; u0 = 36.0; u1 = u0 + SH_STIRRUP_LEG; bot = top - hv
    msp.add_lwpolyline([P((u0, top)), P((u1, top)), P((u1, bot))], dxfattribs=dict(layer='57_HATAH_ZIUN'))
    def dm(base, p1, p2, ang, text=None):
        kw = dict(text=text) if text else {}
        msp.add_linear_dim(base=P(base), p1=P(p1), p2=P(p2), angle=ang, dimstyle=BARZEL_ABOVE, dxfattribs={'layer': Ly['dim']}, **kw).render()
    dm((u1, top), (u0, top), (u1, top), 0); dm((u1, top), (u1, bot), (u1, top), 90, ('H+%g' % (h - 2 * BAR_COVER)) if sym else None)
    L = SH_STIRRUP_LEG + hv; Ltxt = ('L=H+%g' % (SH_STIRRUP_LEG + h - 2 * BAR_COVER)) if sym else 'L=%g' % L
    msp.add_text(' &8@15 ' + Ltxt, height=6.0, dxfattribs=dict(layer='54_HATAH_TEXT', style='HEBTXT', width=0.8, rotation=90.0, insert=P((u1 + 8.0, bot + 2.0))))      # the vertical dim text sits left of its line: the note goes on the right of it, along the leg (as in the user's example)
    # USER CORRECTION 2026-10-22: the two boxes flank the section on ONE line at the downstand-bottom level: OUTSIDE (חוץ) right of the end face (u 33.3..61.7), INSIDE (פנים) left (u -78.7..-50.4); v -h-5.3 .. -h+7.7
    for bx0, raw, tu, tv in ((33.3, 'ju.', 55.3, -1.5), (-78.7, 'pbho', -55.8, -2.4)):
        bx1 = bx0 + 28.4; by0 = -h - 4.7
        msp.add_lwpolyline([P((bx0, by0)), P((bx1, by0)), P((bx1, by0 + 13.0)), P((bx0, by0 + 13.0))], close=True, dxfattribs=dict(layer='55_HATAH_TEXT'))
        msp.add_text(raw, height=6.0, dxfattribs=dict(layer='55_HATAH_TEXT', style='SIVAN', width=0.8, text_generation_flag=2, insert=P((tu, -h + tv))))


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# THICK free edge (D >= THICK_D): the user's own 4-4 for D=80 (red cloud 2026-10-22, brenda_karka, cloud 24D04). Local coordinates u (from the end face, negative = into the slab), v (from the soffit).
THICK_D = 60.0                       # UNVERIFIED threshold; evidence = one example, D=80
FREE_EDGE_MESH = os.environ.get('FREE_EDGE_MESH') == '1'               # user 2026-10-24: NO restraint mesh anywhere, also not on the thick free edge (his 4-4 template had it); code kept, switch on only if he asks again
T_L, T_DOTS, T_X0 = 143.1, 10, -4.3  # shown length; 10 dots / row, step 15, first 4.3 from the face
BENCH_SCALE, BENCH_RIGHT_U, BENCH_BOTTOM_V = 0.5, -168.9, -98.0     # plan detail copied at 1:2 (plan 1:50 -> sheet 1:25), frame right edge / bottom relative to the end face / soffit
BENCH_LAYERS = ('57_HATAH_ZIUN', '44_TEXT_ZIUN', '4_TEXT')
ARROW_OVR = [(1000, 'DSTYLE'), (1002, '{'), (1070, 41), (1040, 1.0), (1070, 147), (1040, 1.5), (1070, 77), (1070, 0), (1002, '}')]


def find_bench_detail(doc, cut):
    """the plan's shear-bench detail near the cut: the biggest closed 57_HATAH_ZIUN frame within 1500 of it (the note says "whole slab area") -> (frame bbox, entities)."""
    from ezdxf import bbox as BB
    msp = doc.modelspace(); best = None
    for e in msp.query('LWPOLYLINE'):
        if e.dxf.layer != '57_HATAH_ZIUN' or not e.closed: continue
        b = BB.extents([e])
        if not b.has_data or (b.extmax.x - b.extmin.x) < 60 or (b.extmax.y - b.extmin.y) < 60: continue
        c = ((b.extmin.x + b.extmax.x) / 2, (b.extmin.y + b.extmax.y) / 2); dd = ((c[0] - cut[0]) ** 2 + (c[1] - cut[1]) ** 2) ** .5
        if dd < 1500 and (best is None or dd < best[0]): best = (dd, b)
    if not best: return None, []
    b = best[1]; x0, x1, y0, y1 = b.extmin.x - 5, b.extmax.x + 5, b.extmin.y - 5, b.extmax.y + 60
    ents = []
    for e in msp:
        if e.dxf.layer not in BENCH_LAYERS or e.dxftype() not in ('TEXT', 'LWPOLYLINE', 'LINE'): continue
        bb = BB.extents([e])
        if bb.has_data and x0 <= bb.extmin.x and bb.extmax.x <= x1 and y0 <= bb.extmin.y and bb.extmax.y <= y1: ents.append(e)
    return (b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y), ents


def draw_thick(doc, D, ex, ey, tmpl, cut=None):
    msp = doc.modelspace(); Ly = LB.PROF['layers']; P = lambda p: (ex + p[0], ey + p[1]); z = '56_HATAH_ZET'
    line = lambda a, b, lay: msp.add_line(P(a), P(b), dxfattribs=dict(layer=lay))
    poly = lambda pts, lay: msp.add_lwpolyline([P(p) for p in pts], dxfattribs=dict(layer=lay))
    for a, b in (((-T_L, D), (0, D)), ((-T_L, 0), (0, 0)), ((0, 0), (0, D))): line(a, b, Ly['outline_new'])
    zig = [(x, y * D / 25.0) if i else (x, y) for i, (x, y) in enumerate(LB.PROF['outline']['zigzag_slab25'])] + [(0, -(D + LB.PROF['outline']['zigzag_below_slab']))]
    poly([(-T_L - x, D + y) for x, y in zig], Ly['break'])
    for y in (BAR_COVER, D - BAR_COVER): line((-T_L, y), (-EDGE_STOP, y), '57_HATAH_ZIUN')
    poly([(-EDGE_STOP, D - BAR_COVER), (-EDGE_STOP, BAR_COVER)], '57_HATAH_ZIUN')
    dot = lambda x, y: LB.add_dot(msp, *P((x, y)), '57_HATAH_ZIUN')
    for k in range(T_DOTS): dot(T_X0 - 15 * k, D - 4.1); dot(T_X0 - 15 * k, 4.4)                                   # top / bottom rows
    mid = D / 2.0
    if FREE_EDGE_MESH:
        poly([(-143.3, mid + 0.1), (-10.0, mid + 0.1)], 'HATAH_ZIUN_17'); poly([(-142.0, mid + 2.1), (-20.1, mid + 2.1)], '2000_DOT_HELP_LINE')   # restraint mesh bar + dashed help line
        for k in range(9): dot(-140.1 + 15 * k, mid + 2.1)                                                          # restraint mesh dots
    for k in range(3): dot(T_X0, mid + 0.2 + 20 * (k - 1))                                                          # edge bars $12@20 (cut ends)

    def txt(raw, x, y, style, h=6.0, w=0.8, gen=0):
        at = dict(layer=Ly['text'], style=style, width=w, insert=P((x, y)))
        if gen: at['text_generation_flag'] = gen
        msp.add_text(raw, height=h, dxfattribs=at)
    # restraint mesh note: shelf + two arrow leaders to the mesh bar start
    if FREE_EDGE_MESH:
        sy = mid - 13.6; poly([(-119.5, sy), (-76.8, sy)], z)
        txt('#\xa410@15\\15', -117.5, sy + 1.5, 'HEBREW_NEW'); txt('ra, rhxui', -78.1, sy - 7.4, 'SIVAN18', gen=2)
        for tip in ((-125.1, mid + 0.9), (-140.1, mid + 2.1)):
            ld = msp.add_leader([P(tip), P((-119.5, sy)), P((-76.8, sy))], dimstyle='DIM25', dxfattribs={'layer': z})
            ld.set_xdata('ACAD', [(1000, 'DSTYLE'), (1002, '{'), (1070, 77), (1070, 0), (1002, '}')])
    # edge bars note
    line((6.5, mid + 9.7), (36.3, mid + 9.7), z); poly([(6.5, mid + 9.7), (T_X0, mid + 0.2)], z); poly([(6.5, mid + 9.7), (T_X0, mid + 0.2 - 20)], z); txt('$12@20', 8.9, mid + 11.6, 'HEBREW_NEW')
    # top / bottom bar notes ("per plan"), elbow heights as in the example
    ey_t = D + 23.0; line((-116.8, ey_t), (-162.1, ey_t), z); poly([(-116.8, ey_t), (T_X0 - 15 * 6, D - 4.1)], z); poly([(-116.8, ey_t), (-74.7, D - 3.0)], z)
    a = dict(tmpl['tp_cast']); a.update(layer=Ly['text'], insert=P((-118.3, ey_t + 1.4))); msp.add_text('c/g/ kph ,fw', height=a.pop('height'), dxfattribs=a)
    ey_b = -29.0; line((-19.0, ey_b), (26.0, ey_b), z); poly([(-19.0, ey_b), (T_X0 - 15 * 2, 4.4)], z); poly([(-19.0, ey_b), (-60.5, 3.0)], z)
    a = dict(tmpl['bt_cast']); a.update(layer=Ly['text'], insert=P((24.3, ey_b + 1.4))); msp.add_text('c/,/ kph ,fw', height=a.pop('height'), dxfattribs=a)
    # overall thickness dim on the RIGHT of the end face
    Dm = LB.PROF['dim']
    msp.add_linear_dim(base=P((53.7, D)), p1=P((0, 0)), p2=P((0, D)), angle=90, dimstyle=Dm['style'], override=Dm['override'], dxfattribs={'layer': Ly['dim']}).render()
    # U bar shape + the slab bars it laps with (legs 100, L = 2*100 + D - 6), below the section
    L_U = 100.0; v0 = -137.5; v1 = v0 + D - 6; ue, us = -3.2, -3.2 - L_U
    poly([(us, v0), (ue, v0), (ue, v1), (us, v1)], 'HATAH_ZIUN_17')
    for vb in (-51.6, -155.2):
        poly([(-134.3, vb), (-3.8, vb)], 'HATAH_ZIUN_17')
        msp.add_lwpolyline([(*P((-134.3, vb + 5.6)), 0.58), (*P((-134.3, vb)), -0.57), (*P((-134.3, vb - 5.6)), 0)], format='xyb', dxfattribs=dict(layer='HATAH_ZIUN_17'))   # wave break at the bar end

    def dm(base, p1, p2, ang): msp.add_linear_dim(base=P(base), p1=P(p1), p2=P(p2), angle=ang, dimstyle=BARZEL_ABOVE, dxfattribs={'layer': Ly['dim']}).render()
    dm((ue, v1), (us, v1), (ue, v1), 0); dm((ue, v0), (us, v0), (ue, v0), 0); dm((ue, v1), (ue, v0), (ue, v1), 90)
    txt('c/g/ kph ,fbh,', -62.6, -49.0, 'SIVAN18', gen=2); txt('c/,/ kph ,fbh,', -61.9, -162.9, 'MIRYL', w=0.85); txt('kph c/g/', -27.0, -72.8, 'SIVAN18', gen=2); txt(' L=%g' % (2 * L_U + D - 6), -90.7, -72.3, 'HEBREW_NEW')
    # shear benches: the plan's detail copied at 1:2 to the left + an arrow leader into the slab
    note = 'no shear-bench detail found in the plan near the cut'
    if cut:
        fr, ents = find_bench_detail(doc, cut)
        if fr:
            from ezdxf.math import Matrix44
            tx = ex + BENCH_RIGHT_U - BENCH_SCALE * fr[2]; ty = ey + BENCH_BOTTOM_V - BENCH_SCALE * fr[1]
            m = Matrix44.scale(BENCH_SCALE, BENCH_SCALE, 1) @ Matrix44.translate(tx, ty, 0)
            for e in ents:
                c = e.copy(); msp.add_entity(c); c.transform(m)
            ld = msp.add_leader([P((-64.9, min(17.3, D / 4.0))), P((-134.4, -39.8)), P((BENCH_RIGHT_U, -39.8))], dimstyle='dim_25', dxfattribs={'layer': z}); ld.set_xdata('ACAD', ARROW_OVR)
            note = '%d plan entities copied (shear benches, 1:2)' % len(ents)
    return note


def main(argv=None, doc=None):
    """argv / doc (batch use, star_plan): draw into the already open `doc` and do not save"""
    a = argparse.ArgumentParser(); a.add_argument('file'); a.add_argument('name'); a.add_argument('--profile', default='israeli-structural'); a.add_argument('--box', nargs=4, type=float, required=True)
    a.add_argument('--slab', type=float, required=True); a.add_argument('--d-label', help="write this symbol (H) instead of the number on the thickness dim: the plan gives no D"); a.add_argument('--cut', nargs=2, type=float, help='cut mid-point X Y: finds the plan shear-bench detail for a thick edge'); a.add_argument('--slab-side', choices=['left', 'right'], default='left', help='slab on the LEFT (user detail) or RIGHT of the view (mirror image)'); a.add_argument('--replace', action='store_true'); a.add_argument('-o'); a.add_argument('--png'); a.add_argument('--note'); a.add_argument('--detail', choices=['none', 'plan', 'ss'], default='none'); a.add_argument('--shutter', nargs=2, type=float, metavar=('B', 'H'), help='roller-shutter downstand b x h at the free end (plan text on automatic_Roller_shutter)')
    a = a.parse_args(argv); LB.apply_profile(a.profile)
    global SHUTTER; SHUTTER = tuple(a.shutter) if a.shutter else None
    bx0, by0, bw, bh = a.box; D = a.slab; S = 1 if a.slab_side == 'left' else -1; ex, ey = (bx0 + EDGE_X if S == 1 else bx0 + bw - EDGE_X), by0 + SOFFIT_Y
    batch = doc is not None; doc = doc if batch else ezdxf.readfile(a.file); tmpl = LB.template_texts(doc)
    if a.replace: print('cleared', LB.clear_cell(doc, (bx0, by0, bx0 + bw, by0 + bh)), 'old entities')
    if a.replace:                                          # LEADER entities (arrow leaders of the thick detail) are not touched by clear_cell
        n_ld = 0
        for e in list(doc.modelspace().query('LEADER')):
            v = list(e.vertices)
            if v and all(bx0 <= p[0] <= bx0 + bw and by0 <= p[1] <= by0 + bh for p in v): doc.modelspace().delete_entity(e); n_ld += 1
        print('cleared', n_ld, 'leaders')
    global D_LABEL; D_LABEL = a.d_label
    thick = D >= THICK_D and S == 1 and not a.d_label
    if thick:
        ex = bx0 + bw / 2.0 + 93.0                       # content spans ex-246 .. ex+60: centred in the cell
        print(draw_thick(doc, D, ex, ey, tmpl, tuple(a.cut) if a.cut else None))
    else: draw(doc, D, ex, ey, tmpl, S)
    a.nosave = True; a.box = [bx0, by0, bw, bh]
    LB.finish(doc, a, ex, ey, 0, D, (-61.3 if thick else -11.2 * S), (-60.0 if thick else MARK_TIP_U * S))       # centre -11.2 = title x of the example
    T = LB.PROF['title']
    for t in doc.modelspace().query('TEXT'):                  # the example's title block sits 1.6 higher than the beam sections' formula
        if bx0 < t.dxf.insert.x < bx0 + bw and by0 < t.dxf.insert.y < by0 + bh and t.dxf.layer == LB.PROF['layers']['text'] and (t.dxf.text.startswith(T['prefix']) or t.dxf.text == T['scale_text']['text']):
            t.dxf.insert = (t.dxf.insert.x, t.dxf.insert.y + 1.6, t.dxf.insert.z)
    if batch: print(f'{a.name}: free slab edge D={D:.0f}'); return
    out = a.o or a.file
    if out == a.file: LB.backup(a.file, 'slabedge-' + a.name)
    doc.saveas(out); print('saved', out, '| audit errors', LB.audit_saved(out)); print(f'{a.name}: free slab edge D={D:.0f}')
    if a.png: LB.render_png(doc, (ex - 130, ex + 60, ey - 110, ey + 130), a.png)

if __name__ == '__main__': main()
