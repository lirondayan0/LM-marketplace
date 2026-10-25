"""Recipe: the GENERAL simple cast beam with a SOLID slab on both sides (the user's section 6-6, parametric: B, D, H(min=40cm), B-6, H-6) for ANY B / D / H.
  python general_beam.py FILE N-N --box X0 Y0 W H --B 25 --D 20 [--H 40] [--h-label h] [--labels example] [--replace] [-o OUT] [--png OUT]
User 2026-10-15 (star marker on a beam WITHOUT a dimension tag b/h): "set the width from the geometry and define the section height with the height parameter 'h'" -> B = measured from the plan,
H drawn at the parametric MINIMUM 40 cm (6-6 labels it H(min=40cm); UNVERIFIED reading) and the height dimensions carry the symbol `h` (overall height `h`, stirrup height `h-6`) instead of a number;
the widths B, B-6 and the slab D are numeric. `--labels example` reproduces 6-6 itself (labels B, H(min=40cm), D, B-6, H-6): `tests` compare it entity by entity with the user's cell.
Geometry (u, v from the beam's left face / soffit; every number measured on 6-6, B=20, D=25, H=74): solid slab both sides 58.9 long with zigzag breaks, bar lines 3 from the slab faces through the beam,
open stirrup B-6 x H-6 with hook, beam dots at 4.4 / B-4.35 (top H-4.3, slab soffit +4.4, then every 20 down, bottom 4.5), slab dot rows (4 per side, step 15, first 9.9 from the face), notes 4$12 / 2$12 / 2$8@20,
top / bottom 'per plan' notes on both slabs, stirrup elevation (two halves B-6 wide, H-6 tall) to the right with the table note (`$12@15`, transfer `$12/14/16@15`), MH level marker with 'per plan', dims B / H / D."""
import argparse, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ezdxf
import ledge_beam as LB
from dxflib import encode
import dxflib as DL

SLAB_END, COL_L, COL_R, TOP_IN, BOT_IN, SOFFIT_IN = 58.9, 4.4, 4.35, 4.3, 4.5, 4.4
DOT_W, DOT_LEN, DOT_FIRST, DOT_STEP, DOT_N, COL_STEP, COL_MIN = 1.25, 1.3, 9.9, 15.0, 4, 20.0, 8.0
CLOSED_MAX_H = 100.0                            # beam height up to which the stirrup elevation is ONE closed stirrup (user 2026-10-25); above it the two halves
ST_X, ST_GAP = 52.8, 4.5                        # stirrup elevation starts 52.8 right of the slab end (was 22.1: its '74' dim sat ON the slab-thickness dim line; user 2026-10-25 moved it +30.7 in korchakk 1-1, +16.7 in 4-4), halves 4.5 apart
CELL_U0, CELL_V0 = 179.7, 248.8                 # beam origin inside the 400 x 450 cell (user's 6-6, B=20)
MIN_H = 40.0                                    # 'H(min=40cm)' of the 6-6 label

BOTTOM_BAR_INTO_BEAM = 60.0
MH_X = 5.0                                      # level marker stem: 5 right of the beam's left face (user 2026-10-25), every beam width; its texts end 0.8 left of the stem
MH_SHIFT, MH_SHIFT_MIN_B = 0.0, 60.0
OVERLAY = False   # user 2026-10-22: section over a Revit XREF - reinforcement only (no outline, breaks, dims of the section, level marker, title)
RESTRAINT_MESH = False   # user 2026-10-22 (later): 'there is no restraint grid in the ceilings' - REMOVED from cross-sections; code kept, switch on only if he asks again
THICK_D = 60.0     # threshold of the restraint mesh, used ONLY if RESTRAINT_MESH is switched on (it is off: user 2026-10-22 'no restraint grid in the ceilings'); the thick FREE edge (slab_edge.draw_thick) has no mesh either since 2026-10-24 (slab_edge.FREE_EDGE_MESH)

def beam_dot_rows(H, D, step=None, fill_gap=False):
    """v positions of the beam bar dots: top, slab soffit + 4.4, then every 20 down while 8+ above the bottom row, bottom 4.5 (6-6: 69.7, 53.4, 33.4, 13.4, 4.5 for H=74, D=25).
    fill_gap (user 2026-10-22, 12-12: 'a central reinforcing bar is missing'): when a slab sits LOWER than the beam top (the beam face is exposed above it) and the gap between the top row and the soffit row exceeds the
    middle-steel spacing, the missing side-face rows are added evenly in between (12-12: gap 51 -> 3 rows at 12.8); they join the middle rows (index >= 2), top / soffit / bottom keep their places."""
    yt, y2 = H - TOP_IN, H - D + SOFFIT_IN; step = step or COL_STEP; ys = [yt, y2]; y = y2 - step
    while y - BOT_IN >= COL_MIN: ys.append(y); y -= step
    if ys[-1] - BOT_IN > 0.5: ys.append(BOT_IN)
    if fill_gap and yt - y2 > 1.5 * step:      # a D=25 slab (gap 16.3) is the accepted standard; a real hole is > 1.5 x the spacing
        n = math.ceil((yt - y2) / step - 1e-9) - 1; extra = [yt - (yt - y2) * k / (n + 1) for k in range(1, n + 1)]
        ys = ys[:2] + sorted(extra + ys[2:-1], reverse=True) + ys[-1:]
    return ys

def draw(doc, B, D, H, ox, oy, name, tmpl, lab, centre_u, stirrups='standard', Dl=None, Dr=None, dl=0.0, dr=0.0, sides='both'):
    msp = doc.modelspace(); Ly = LB.PROF['layers']; P = lambda p: (ox + p[0], oy + p[1]); z = '56_HATAH_ZET'; zi = '57_HATAH_ZIUN'
    line = lambda a, b, lay: msp.add_line(P(a), P(b), dxfattribs=dict(layer=lay))
    poly = lambda pts, lay: msp.add_lwpolyline([P(p) for p in pts], dxfattribs=dict(layer=lay))
    def txt(raw, key, x, y, **kw):
        a = dict(tmpl[key]); a.update(layer=Ly['text'], insert=P((x, y))); a.update(kw); msp.add_text(raw, height=a.pop('height'), dxfattribs=a)
    R, Lft = B + SLAB_END, -SLAB_END
    # PER-SIDE slabs (user 2026-10-21: 'double-check the ceiling thicknesses'): each side has its own thickness (Dl / Dr) and may sit lower than the beam top (dl / dr = beam top - slab top); defaults = D, 0
    Dl = D if Dl is None else Dl; Dr = D if Dr is None else Dr; yTl, yTr = H - dl, H - dr; ySl, ySr = yTl - Dl, yTr - Dr
    hasL, hasR = sides in ('both', 'left'), sides in ('both', 'right')      # 2026-10-23: a wall (no slab) on one side of the beam - XREF Sec 26: sides='left'
    D = min([v for v, ok in ((dl + Dl, hasL), (dr + Dr, hasR)) if ok]); yS = H - D                              # depth of the shallower slab soffit: the beam's own bar rows follow it
    # outline: beam below the slab, slab soffit and top lines both sides, top line through the beam
    if not (hasL and hasR):      # a FREE EDGE on one side (korchakk 2026-10-23: 9_KONTUR on the beam face = edge beam): the beam face runs to the top there, only the existing side carries a slab
        _ol = [((0, 0), (B, 0)), ((0, H), (B, H))] + ([((0, ySl), (0, 0)), ((0, ySl), (Lft, ySl)), ((0, yTl), (Lft, yTl))] + ([((0, yTl), (0, H))] if dl > 0 else []) if hasL else [((0, 0), (0, H))]) \
            + ([((B, 0), (B, ySr)), ((B, ySr), (R, ySr)), ((B, yTr), (R, yTr))] + ([((B, yTr), (B, H))] if dr > 0 else []) if hasR else [((B, 0), (B, H))])
    elif dl == 0 and dr == 0 and Dl == Dr: _ol = (((0, yS), (0, 0)), ((0, 0), (B, 0)), ((B, 0), (B, yS)), ((B, yS), (R, yS)), ((0, H), (R, H)), ((0, yS), (Lft, yS)), ((B, H), (Lft, H)))
    else: _ol = (((0, ySl), (0, 0)), ((0, 0), (B, 0)), ((B, 0), (B, ySr)), ((B, ySr), (R, ySr)), ((0, ySl), (Lft, ySl)), ((0, H), (B, H)), ((B, yTr), (R, yTr)), ((0, yTl), (Lft, yTl))) + ((((B, yTr), (B, H)),) if dr > 0 else ()) + ((((0, yTl), (0, H)),) if dl > 0 else ())
    for a, b in ([] if OVERLAY else _ol): line(a, b, Ly['outline_new'])
    _zg = lambda Ds: [(x, y * Ds / 25.0) if i else (x, y) for i, (x, y) in enumerate(LB.PROF['outline']['zigzag_slab25'])] + [(0, -(Ds + LB.PROF['outline']['zigzag_below_slab']))]
    if not OVERLAY and hasR: poly([(R + x, yTr + y) for x, y in _zg(Dr)], Ly['break'])
    if not OVERLAY and hasL: poly([(Lft - x, yTl + y) for x, y in _zg(Dl)], Ly['break'])
    _anc = min(BOTTOM_BAR_INTO_BEAM, B - 3)          # user 2026-10-21 (3-3 cloud + 60 dim): slab bars enter the beam 60 from the face (top bars too since 2026-10-24, see below)
    # user 2026-10-24 (red cloud on netivot 7-7, lower-left slab top bar drawn through the whole 130 beam; 'a solid slab beside a beam: its bars go 60 into the beam'): a TOP bar enters 60 too, EXCEPT where both slab tops are flush
    # (one continuous slab top over the beam: the bar runs through, as before). One-sided slab or different top levels (stepped) -> 60 from the face it enters through (W-3 if narrower).
    _flush = hasL and hasR and abs(yTl - yTr) < 0.5
    _tR = 3 if _flush else B - _anc; _tL = B - 3 if _flush else _anc
    if hasR: line((B - _anc, ySr + 3), (R, ySr + 3), zi); line((_tR, yTr - 3), (R, yTr - 3), zi)                  # slab bar lines (each side at its own levels)
    if hasL: line((_anc, ySl + 3), (Lft, ySl + 3), zi); line((_tL, yTl - 3), (Lft, yTl - 3), zi)
    _n, _w, _, _ = LB.stirrup_layout(B, stirrups); LB.draw_stem_stirrups(msp, P, B, H, _n, _w, zi, closed_top=False)   # the table's stirrups inside the section (standard 65 -> 2 x 40)
    def dot(cx, y, sgn): msp.add_lwpolyline([(ox + cx - sgn * DOT_LEN / 2, oy + y, 0, 0, -sgn), (ox + cx + sgn * DOT_LEN / 2, oy + y, 0, 0, -sgn)], format='xyseb', close=True, dxfattribs=dict(layer=zi, const_width=DOT_W))
    _md, _ms, _mnote = DL.mid_steel(B, H)            # middle steel by section area (user 2026-10-21)
    rows = beam_dot_rows(H, D, _ms, fill_gap=(dl > 0 or dr > 0))
    for y in rows: dot(COL_L, y, 1); dot(B - COL_R, y, 1)
    if B > 30:       # WIDE beam (user 2026-10-21, red clouds on the 150-wide 1-1: 'missing its rebar detailing'): the top row and the bottom row run ACROSS the width, equal steps <= the taught maxima (top 5.9, bottom 10.15 - ledge_beam SP_T / SP_B); B=20 keeps the user's 6-6 pair
        for y, sp in ((rows[0], 5.9), (rows[-1], 10.15)):
            span = (B - COL_R) - COL_L; n = max(1, math.ceil(span / sp - 1e-9))
            for k in range(1, n): dot(COL_L + span * k / n, y, 1)
    for y in ((yTr - TOP_IN, ySr + SOFFIT_IN) if hasR else ()):
        for k in range(DOT_N): dot(B + DOT_FIRST + DOT_STEP * k, y, 1)
    for y in ((yTl - TOP_IN, ySl + SOFFIT_IN) if hasL else ()):
        for k in range(DOT_N): dot(-(DOT_FIRST + 0.05) - DOT_STEP * k, y, -1)
    # RESTRAINT MESH (user 2026-10-22: 'ceilings of 60 cm or more need a restraint mesh'): per slab side with D >= THICK_D - a mid-depth bar + help line + dots in the same columns as the slab rows, note '#$10@15\\15 + restraint mesh' with two arrow leaders (his 4-4 detail, slab_edge.draw_thick)
    def restraint_mesh(sgn, D_, yT_):
        ym_ = yT_ - D_ / 2.0; xs_ = [(B + DOT_FIRST + DOT_STEP * k) if sgn > 0 else -(DOT_FIRST + 0.05) - DOT_STEP * k for k in range(DOT_N)]
        e0 = B + 3 if sgn > 0 else -3; e1 = R if sgn > 0 else Lft
        poly([(e0, ym_ + 0.1), (e1, ym_ + 0.1)], 'HATAH_ZIUN_17'); poly([(xs_[0], ym_ + 2.1), (xs_[-1], ym_ + 2.1)], '2000_DOT_HELP_LINE')
        for x_ in xs_: dot(x_, ym_ + 2.1, sgn)
        sy_ = ym_ - 13.6; xe_ = (B + 84.0) if sgn > 0 else (Lft - 17.0); xf_ = xe_ + sgn * 42.7      # left note starts just beyond the left thickness dim (Lft - 14.4) so it stays inside the 400 cell
        poly([(xe_, sy_), (xf_, sy_)], z)
        at = dict(layer=Ly['text'], style='HEBREW_NEW', width=0.8); msp.add_text('#\xa410@15\\15', height=6.0, dxfattribs=dict(at, insert=P((min(xe_, xf_) + 2.0, sy_ + 1.5))))
        msp.add_text('ra, rhxui', height=6.0, dxfattribs=dict(layer=Ly['text'], style='SIVAN18', width=0.8, text_generation_flag=2, insert=P((max(xe_, xf_) - 1.3, sy_ - 7.4))))
        for tip in ((xs_[2] + sgn * 7.5, ym_ + 0.9), (xs_[3], ym_ + 2.1)):
            ld = msp.add_leader([P(tip), P((xe_, sy_)), P((xf_, sy_))], dimstyle='DIM25', dxfattribs={'layer': z})
            ld.set_xdata('ACAD', [(1000, 'DSTYLE'), (1002, '{'), (1070, 77), (1070, 0), (1002, '}')])
    if RESTRAINT_MESH and Dr >= THICK_D: restraint_mesh(1, Dr, yTr)
    if RESTRAINT_MESH and Dl >= THICK_D: restraint_mesh(-1, Dl, yTl)
    # notes (offsets measured on 6-6)
    yt, y2 = rows[0], rows[1]; xl, xr = COL_L, B - COL_R
    ex, ey = B + 4.0, H + 17.3                                                                       # 4$12: top pair + slab-soffit pair
    WIDE = B > 30      # user 2026-10-21 (hand-organised 1-1 and 2-2 of brenda_karka): on wide beams the top note keeps ONLY its two forks to the top bar row (array); the soffit-row forks are gone
    for x, y in (((xl, yt), (xr, yt)) if WIDE else ((xl, yt), (xr, yt), (xl, y2), (xr, y2))): line((ex, ey), (x, y), z)
    poly([(ex, ey), (ex + 23.6, ey)], z); txt('4$12', 'c4', ex + 3.4, ey + 0.7)
    ex, ey = B + 4.5, -5.6                                                                           # 2$12 bottom pair
    _eyB = ySr + SOFFIT_IN - 16.7      # the right slab's bottom note (drawn below): on a WIDE beam with slab on the right its shelf sits within ~3 of this one and the two notes overlapped (netivot 9-9)
    if hasR and WIDE and abs(ey - _eyB) < 9.2: ex, ey = B - 1.2, _eyB - 9.2       # his hand edit of netivot 9-9 (B=130): the beam-bottom note 9.2 BELOW the slab-bottom note, joint 5.7 further left (1 example, UNVERIFIED beyond it)
    for x in (xl, xr): line((ex, ey), (x, BOT_IN), z)
    poly([(ex, ey), (ex + 21.9, ey)], z); txt('2$12', 'c2', ex + 2.9, ey + 0.7)
    mids = [y for y in rows[2:-1]]
    if mids:                                                                                         # 2$8@20 on the first mid pair
        ym = mids[1] if (WIDE and len(mids) > 1) else mids[0]; ex, ey = -5.3, ym - 11.5        # wide beams: the user moved the 2$8@20 forks one row DOWN (1-1 / 2-2: second skin pair)
        # NO INTERFERENCE (user 2026-10-22, his hand-fixed 3-3 = the example): the middle-steel note never overlaps another note, a fork or the slab; the OTHER notes keep their default places, THIS note yields:
        # if the nominal row collides, the forks move to the clear mid row nearest the MIDDLE of the exposed face (3-3: row 74.4 -> 44.4, note 63.6 -> 33.2)
        def _clear(r):
            e_ = r - 11.5; shelf_ = (ex - 32.0, e_ - 0.8, ex, e_ + 0.8); txt_ = (ex - 31.0, e_ + 0.5, ex - 4.0, e_ + 7.5); y2l_ = ySl + SOFFIT_IN
            bad = [(Lft - 8, ySl - 1.5, 2, yTl + 1.5),                              # the left slab band (outline + bar lines)
                   (-74.5, yTl + 7.0, -28.0, yTl + 15.5), (-31.0, yTl - 5.0, -9.0, yTl + 8.0),      # top-left slab note + its forks
                   (-65.0, y2l_ - 21.5, -8.0, y2l_ + 1.0)] if hasL else []                          # bottom-left slab note, shelf and forks
            hit = lambda a, b: a[0] - 1.5 < b[2] and b[0] < a[2] + 1.5 and a[1] - 1.5 < b[3] and b[1] < a[3] + 1.5
            return not any(hit(shelf_, b_) or hit(txt_, b_) for b_ in bad)
        side = 'L'
        if not _clear(ym):
            ok = [r for r in mids if _clear(r)]
            if ok: ym = min(ok, key=lambda r: abs(r - ySl / 2.0)); ey = ym - 11.5
            else:
                # the left side is crowded (user 2026-10-22, his hand-fixed 11-11): the note moves to the OTHER side of the beam - joint B + 11.3, shelf running right, nominal row kept, joint 18.7 below the row (11-11: joint y 50.7 for row 69.4)
                y2r_ = ySr + SOFFIT_IN
                def _clear_r(r, off):
                    e_ = r - off; shelf_ = (B + 11.3, e_ - 0.8, B + 43.2, e_ + 0.8); txt_ = (B + 13.0, e_ + 0.5, B + 42.5, e_ + 7.5)
                    bad = [(B - 2, ySr - 1.5, B + SLAB_END + 8, yTr + 1.5), (B + 9.0, yTr - 5.0, B + 75.0, yTr + 14.0), (B + 8.0, y2r_ - 21.0, B + 66.0, y2r_ + 1.0), (B + 3.0, -7.6, B + 32.0, 3.4)] if hasR else []      # + the bottom-pair note 2$12 (joint B + 4.5, shelf y -5.6): the middle-steel note must not sit on it (XREF Sec 17, 2026-10-23)      # right slab band, top-right note + forks, bottom-right note + forks
                    hit = lambda a, b: a[0] - 1.5 < b[2] and b[0] < a[2] + 1.5 and a[1] - 1.5 < b[3] and b[1] < a[3] + 1.5
                    return not any(hit(shelf_, b_) or hit(txt_, b_) for b_ in bad)
                cand = [(r, off) for r in sorted(mids, key=lambda r: abs(r - ym)) for off in (18.7, 11.5, 26.0, 33.0) if _clear_r(r, off)]
                if cand: side = 'R'; ym, off_ = cand[0]; ey = ym - off_; ex = B + 11.3
                else: print(f'WARNING {name}: no clear place for the middle-steel note on either side - nominal kept (check by eye)')
        for x in (xl, xr): line((x, ym), (ex, ey), z)
        if side == 'R': line((ex, ey), (ex + 31.9, ey), z); txt(_mnote, 'c28', ex + 2.4, ey + 1.0)
        else: line((ex, ey), (ex - 31.9, ey), z); txt(_mnote, 'c28', ex - 30.4, ey + 1.0)
    y2r, y2l = ySr + SOFFIT_IN, ySl + SOFFIT_IN
    ex, ey = B + 28.8, yTr + 5.6                                                                     # right slab top: forks to the first dot and the mesh line
    if hasR: line((B + 10.5, yTr - TOP_IN), (ex, ey), z); line((B + 21.9, yTr - 3), (ex, ey), z); line((ex, ey), (ex + 45.3, ey), z); txt('c/g/ kph ,fw', 'tp_cast', ex + 43.9, ey + 1.5)
    ex, ey = B + 19.8, y2r - 16.7                                                                    # right slab bottom
    if hasR: line((B + 15.6, ySr + 3), (ex, ey), z); line((B + 9.9, y2r), (ex, ey), z); line((ex, ey), (ex + 45.0, ey), z); txt('c/,/ kph ,fw', 'bt_cast', ex + 44.4, ey + 1.2)
    if hasL: line((-10.6, yTl - TOP_IN), (-28.9, yTl + 7.1), z); line((-28.9, yTl + 7.1), (-74.2, yTl + 7.1), z); txt('c/g/ kph ,fw', 'tp_cast', -30.3, yTl + 8.5)     # left slab
    if hasL: line((-10.0, y2l), (-18.0, y2l - 19.4), z); line((-18.0, y2l - 19.4), (-63.0, y2l - 19.4), z); txt('c/,/ kph ,fw', 'bt_cast', -19.6, y2l - 18.7)
    n_st, w_st, note_st, _ = LB.stirrup_layout(B, stirrups)
    if n_st > 1:                         # the user's tables ask for several stirrups: staggered rectangles under the beam (as the ledge / cast sections), per-table note
        step = (B - 6 - w_st) / (n_st - 1); h6 = H - 6; Bz0 = 'dim_25_BARZEL_Above'
        for i in range(n_st):
            x0 = 3 + i * step; x1 = x0 + w_st; yt_ = LB.DET_TOP - LB.DET_STAGGER * i; yb_ = yt_ - h6
            msp.add_lwpolyline([P(q) for q in ((x1, yt_), (x0, yt_), (x0, yb_), (x1, yb_))], close=True, dxfattribs=dict(layer=zi))
            line((x1 - LB.HOOK_DX, yt_ - LB.HOOK_DY1), (x1 - LB.HOOK_DX, yt_), zi); line((x1, yt_ - LB.HOOK_DY2), (x1 - LB.HOOK_DX2, yt_ - LB.HOOK_DY2), zi)
            msp.add_linear_dim(base=P((x1, yb_)), p1=P((x0, yb_)), p2=P((x1, yb_)), angle=0, dimstyle=Bz0, dxfattribs={'layer': Ly['text']}).render()
            kw = dict(base=P((x1, yt_)), p1=P((x1, yb_)), p2=P((x1, yt_)), angle=90, dimstyle=Bz0, dxfattribs={'layer': Ly['text']}); kw.update({'text': lab['H-6']} if lab['H-6'] else {}); msp.add_linear_dim(**kw).render()
        ylow = LB.DET_TOP - LB.DET_STAGGER * (n_st - 1) - h6
        _t = f"{n_st}{note_st}" + ('' if lab['H-6'] else f" L={round(2 * (w_st + h6) + 12)}"); _sx = 3 - 6.7
        try:                                  # user 2026-10-21 (1-1 / 2-2): the table note is CENTRED under the stirrup group (group 3 .. B-3, centre B/2)
            from shx_width import text_extent; _a, _b = text_extent(tmpl['stirrup']['style'], _t, 0.0, tmpl['stirrup']['height'], tmpl['stirrup'].get('width', 1.0)); _sx = B / 2 - (_a + _b) / 2
        except Exception as _ex: print('WARNING hoop note NOT centred (fallback to the left):', repr(_ex))
        txt(_t, 'stirrup', _sx, ylow - LB.DET_TXT_DY)
    # stirrup elevation to the right: two halves facing each other
    w = B - 6; xa = R + ST_X; xb = xa + w + ST_GAP; xe = xb + w; h = H - 6; ey = 3.0       # ey = bottom edge of the stirrup elevation
    ELEV = n_st == 1
    BELOW = OVERLAY and ELEV      # user 2026-10-25 (3600-CON-11): on an XREF the elevation beside the slab ran into the neighbouring XREF section -> it goes BENEATH its own section (top DET_TOP below the beam bottom, centred on the beam), the two labels under it
    if BELOW: xa = B / 2 - (2 * w + ST_GAP) / 2; xb = xa + w + ST_GAP; xe = xb + w; ey = LB.DET_TOP - h
    CLOSED = ELEV and H <= CLOSED_MAX_H      # user 2026-10-25: H up to 100 -> ONE closed stirrup beside the slab (as the staggered stirrups under a wide beam), above 100 -> the two halves
    if CLOSED:
        if BELOW: xa = B / 2 - w / 2
        xe = xa + w; x1 = xe
        msp.add_lwpolyline([P(q) for q in ((x1, ey + h), (xa, ey + h), (xa, ey), (x1, ey))], close=True, dxfattribs=dict(layer=zi))
        line((x1 - LB.HOOK_DX, ey + h - LB.HOOK_DY1), (x1 - LB.HOOK_DX, ey + h), zi); line((x1, ey + h - LB.HOOK_DY2), (x1 - LB.HOOK_DX2, ey + h - LB.HOOK_DY2), zi)
    else:
        for (p, q) in (((xa, ey + h), (xa + w, ey + h)), ((xa, ey), (xa + w, ey)), ((xb, ey + h), (xe, ey + h)), ((xb, ey), (xe, ey)), ((xa, ey), (xa, ey + h)), ((xe, ey), (xe, ey + h))):
            if ELEV: line(p, q, zi)
    Dm = LB.PROF['dim']; Bz = 'dim_25_BARZEL_Above'
    def dim(base, p1, p2, ang, text=None, style=None, layer=None, **kw):
        if OVERLAY and not style: return          # the XREF carries the section dims; the stirrup-detail (bar) dims keep their style
        kw = dict(base=P(base), p1=P(p1), p2=P(p2), angle=ang, dimstyle=style or Dm['style'], dxfattribs={'layer': layer or Ly['dim']}); kw.update({'text': text} if text else {});
        if not style: kw['override'] = Dm['override']
        msp.add_linear_dim(**kw).render()
    dim((0, -18.2), (0, 0), (B, 0), 0, lab['B'])
    dim((-88.0 if hasL else -56.2, 0), (0, 0), (0, H), 90, lab['H'])      # no slab on the left (free edge): nothing stands between the section and its height dim -> 56.2 (user 2026-10-25, korchakk 2-2: he moved the '50' 31.8 closer, 'too far from the section')
    if hasL: dim((Lft - 14.4, yTl), (Lft, ySl), (Lft, yTl), 90, lab.get('Dl') or lab['D'])
    if hasR: dim((B + 76.8, yTr), (B + 58.9, ySr), (B + 58.9, yTr), 90, lab.get('Dr') or lab['D'])      # user 2026-10-21 (red cloud on 1-1): the RIGHT slab thickness dim measures at the slab end (B + 58.9), its line 17.9 beyond (B + 76.8)
    # SIDE CHAINS (user 2026-10-22, his hand-dimensioned 2-2 = the model; also taught 2026-10-21): every side carries the FULL chain of vertical segments beam bottom -> slab soffit -> slab top -> beam top on the slab-thickness dim line
    # (left x = Lft - 14.4, right x = B + 76.8), the new segments measured at the beam face, text 4.5 outside the line (style default); a zero-length segment is not dimensioned. Identical sides (same D, same level) -> the RIGHT side complete,
    # the left keeps overall height + slab; different sides -> both complete. Symbolic H / D (untagged beams) -> no numeric chain.
    symL, symR = bool(lab.get('Dl') or lab['D']), bool(lab.get('Dr') or lab['D'])      # a side whose thickness is the symbol H gets no numeric chain
    if not lab['H'] and not (symL and symR):
        xL, xR = Lft - 14.4, B + 76.8; both = not (Dl == Dr and dl == dr) or not (hasL and hasR)
        def seg(x, ya, yb, p1, p2): dim((x, ya), p1, p2, 90, location=P((x - 4.5, (ya + yb) / 2)))      # text centre 4.5 outside the line, mid-height (his 2-2: textmid = line x - 4.5)
        if both and hasL and not symL:
            if ySl > 0.5: seg(xL, 0, ySl, (0, 0), (0, ySl))
            if dl > 0.5: seg(xL, yTl, H, (0, yTl), (0, H))
        if hasR and not symR:
            if ySr > 0.5: seg(xR, 0, ySr, (B, 0), (xR, ySr))                  # his 130: one point on the dim line, one on the beam-bottom corner; lower point FIRST (ezdxf puts the text on the wrong side of the line otherwise)
            if dr > 0.5: seg(xR, yTr, H, (B, yTr), (B, H))
    for (x0, x1) in ((((xa, xa + w),) if CLOSED else ((xa, xa + w), (xb, xe))) if ELEV else ()):
        if not CLOSED: dim((x1, ey + h), (x0, ey + h), (x1, ey + h), 0, lab['B-6'], Bz, Ly['text'])
        dim((x1, ey), (x0, ey), (x1, ey), 0, lab['B-6'], Bz, Ly['text'])
    if ELEV:
        if not CLOSED: dim((xa, ey + h), (xa, ey), (xa, ey + h), 90, lab['H-6'], Bz, Ly['text'])
        dim((xe, ey + h), (xe, ey), (xe, ey + h), 90, lab['H-6'], Bz, Ly['text'])
        _hn = LB.stirrup_layout(B, stirrups)[2]; _hl = _hn if lab['H-6'] else f"{_hn} L={round(2 * (w + h) + 12)}"      # taught cast rule: one rectangle L = 2*(B-6 + H-6) + 12 (numeric H only; a symbolic height has no taught L)
        _sx = xa - 1.9
        try:                                  # ONE note, centred under the elevation, 12.6 under its bottom edge (user 2026-10-25, korchakk 1-1 / 4-4: he deleted the second '$12@15' and moved the note below the stirrups)
            from shx_width import text_extent; _a, _b = text_extent(tmpl['st']['style'], _hl, 0.0, tmpl['st']['height'], tmpl['st'].get('width', 1.0)); _sx = (xa + xe) / 2 - (_a + _b) / 2
        except Exception as _ex: print('WARNING stirrup note NOT centred (fallback to the left):', repr(_ex))
        txt(_hl, 'st', _sx, ey - 12.6)        # hoops: S $12@15, ST $12/14/16@15 (user 2026-10-21; was $8@15 of the generic example)
    # level marker (arrow on the beam top, 'per plan') + title and scale
    if OVERLAY: return
    _mh = MH_SHIFT if B >= MH_SHIFT_MIN_B else 0.0      # user 2026-10-24 (his hand edit of 17-17, B=170): the 'o.k per plan' marker + its note sit 18.3 right of the very corner, not on it (1 example; narrow beams keep the corner: UNVERIFIED)
    if 'MH' in doc.blocks: msp.add_blockref('MH', P((MH_X + _mh, H)), dxfattribs=dict(layer='58_HATAH_SIM', xscale=-1.0, yscale=1.0))
    txt('kph ,fw', 'tp_cast', MH_X - 0.8 + _mh, H + 7.3, height=5.0, width=0.7); txt('/K/O', 'tp_cast', MH_X - 0.8 + _mh, H + 14.3, height=5.0, width=0.7, style='SIVAN', text_generation_flag=2)      # 'o.k' over 'per plan' (user 2026-10-25, korchakk 1-1 cloud: he added the 'o.k' line and moved the per-plan line 5.2 down)
    T = LB.PROF['title']; st = T['scale_text']; cx = centre_u
    msp.add_text(T['prefix'] + LB.title_name(name), height=T['height'], dxfattribs=dict(layer=Ly['text'], style=T['style'], width=T['width'], text_generation_flag=T['text_generation_flag'], insert=P((cx + 8.9, H + 55.9))))
    msp.add_text(st['text'], height=st['height'], dxfattribs=dict(layer=Ly['text'], style=st['style'], width=st['width'], insert=P((cx - 26.7, H + 45.5))))

def main(argv=None, doc=None):
    """argv / doc (batch use, star_plan): draw into the already open `doc` and do not save"""
    a = argparse.ArgumentParser(); a.add_argument('file'); a.add_argument('name'); a.add_argument('--profile', default='israeli-structural'); a.add_argument('--box', nargs=4, type=float, required=True)
    a.add_argument('--B', type=float, required=True); a.add_argument('--D', type=float, default=25.0); a.add_argument('--D-left', type=float); a.add_argument('--D-right', type=float); a.add_argument('--drop-left', type=float, default=0.0, help='beam top minus left slab top (cm)'); a.add_argument('--drop-right', type=float, default=0.0); a.add_argument('--H', type=float, default=MIN_H)
    a.add_argument('--d-label', help="symbol (H) written on the slab thickness dims when the plan gives no D"); a.add_argument('--d-label-left', help='same, for the LEFT slab only (the right one has a plan marker)'); a.add_argument('--d-label-right', help='same, RIGHT slab only'); a.add_argument('--sides', choices=['both', 'left', 'right'], default='both', help='which sides carry a slab: the other is a FREE EDGE (beam face = slab edge)'); a.add_argument('--h-label', help="symbol written on the height dimensions instead of a number (user: 'h')"); a.add_argument('--labels', choices=['numeric', 'example'], default='numeric')
    a.add_argument('--stirrups', choices=['standard', 'transfer'], default='standard', help='the user stirrup tables (transfer = a new element rises from the beam)'); a.add_argument('--detail', choices=['none', 'plan', 'ss'], default='none', help='S = as per plan, SS = X$XX notes'); a.add_argument('--replace', action='store_true'); a.add_argument('-o'); a.add_argument('--png'); a = a.parse_args(argv); LB.apply_profile(a.profile)
    B, D, H = a.B, a.D, a.H
    if a.labels == 'example': lab = {'B': 'B', 'H': 'H(min=40cm)', 'D': 'D', 'B-6': 'B-6', 'H-6': 'H-6'}
    else:
        hs = a.h_label; lab = {'B': None, 'H': hs, 'D': a.d_label, 'B-6': None, 'H-6': (hs + '-6') if hs else None, 'Dl': a.d_label_left, 'Dr': a.d_label_right}
    bx0, by0, bw, bh = a.box; ox = bx0 + CELL_U0 - (B - 20) / 2; oy = by0 + CELL_V0
    batch = doc is not None; doc = doc if batch else ezdxf.readfile(a.file); tmpl = LB.template_texts(doc)
    if a.replace:
        print('cleared', LB.clear_cell(doc, (bx0, by0, bx0 + bw, by0 + bh)), 'old entities'); T0 = LB.PROF['title']       # clear_cell keeps titles; this recipe writes its own
        for t in list(doc.modelspace().query('TEXT')):
            if bx0 < t.dxf.insert.x < bx0 + bw and by0 < t.dxf.insert.y < by0 + bh and t.dxf.layer == LB.PROF['layers']['text'] and (t.dxf.text.startswith(T0['prefix']) or t.dxf.text == T0['scale_text']['text']): doc.modelspace().delete_entity(t)
    draw(doc, B, D, H, ox, oy, a.name, tmpl, lab, (B - 20) / 2 + 29.65 - 0.0, a.stirrups, a.D_left, a.D_right, a.drop_left, a.drop_right, a.sides)
    a.box = [bx0, by0, bw, bh]; LB.apply_detail(doc, a)
    if batch: print(f'{a.name}: general beam B={B:g} H={H:g} D={D:g}'); return
    out = a.o or a.file
    if out == a.file: LB.backup(a.file, 'genbeam-' + a.name)
    doc.saveas(out); print('saved', out, '| audit errors', DL.audit_saved(out)); print(f'{a.name}: general beam B={B:g} H={H:g} D={D:g}')
    if a.png: LB.render_png(doc, (ox - 90, ox + B + 150, oy - 40, oy + H + 80), a.png)

if __name__ == '__main__': main()
