"""Recipe: draw a COMPLETE hollow-core beam section (outline, slab dashes, topping mesh, stirrups, bar dots, leaders/notes, dimensions, o.k marker)
in a target cell, following the user's ground-floor examples (frame at x~113146: 2-2 = beam with a 15 ledge each side and slabs both sides; 5-5 = ledge on one side).
  python ledge_beam.py FILE N-N --box X0 Y0 W H --beam W H --slab S --topping T --sides both|right|left [--replace] [--dry] [-o OUT] [--png OUT]
--replace first deletes what an earlier run / section_outline drew in the cell (lines, polylines, dims, o.k marker; keeps the cell frame, titles, user markup).
All geometry is relative to the beam's bottom-left corner; numbers marked (ex 2-2) were measured on that example and reproduced by `--selftest`.
Choose the kind with `scripts/plan_cuts.py`: cut looking ALONG the panel span -> `--kind cast` (cores as circles, panels do not bear on the beam); cut perpendicular to the span -> `--kind ledge` (panels lengthwise on the ledges).
Rules + evidence: ../conventions/section-drawings.md ('Hollow-core beam section'). Bar COUNTS follow max-spacing rules inferred from the examples (UNVERIFIED)."""
import argparse, math, os, shutil, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))      # leader_fit (python -I drops the script dir)
from dxflib import *

PROF = load_profile()

def apply_profile(name):
    """Load profile `name` and override this module's constants with its 'beam_section' block (keys = constant names)."""
    global PROF
    PROF = load_profile(name)
    for k, v in PROF.get('beam_section', {}).items():
        if k in globals():
            globals()[k] = {int(a): b for a, b in v.items()} if k == 'ST_OVERLAP' else (tuple(map(tuple, v)) if k == 'BREAK_L' else v)
SOLID_END, SOLID_DOT0, SOLID_DOT_STEP, SOLID_DOT_N, SOLID_COL, SOLID_TOP_IN, SOLID_SOFFIT_IN = 58.9, 9.9, 15.0, 4, 4.35, 4.3, 4.4     # solid slab beside a ledge beam = the user's 6-6 slab (general_beam.py): 58.9 long, 4 dots per row step 15 from 9.9
LEDGE, SLAB_SHOWN = 15, 45          # ledge width; slab length drawn beyond the beam face (ex 2-2: slab ends 45 from the face)
INSET_BAR, INSET_ST, INSET_TOPBAR = 4.5, 3.0, 4.6      # bar dots / stirrup / top-and-ledge dots (ex 2-2: 4.5, 3, 4.6)
SP_B, SP_T, SP_V, SP_FACE = 10.15, 5.9, 17.0, 23.6     # max dot spacing: bottom row, top row, ledge columns (ex 2-2), plain full-height face (ex 5-5)
STIRRUPS = 'standard'                # 'standard' | 'transfer' = the user's two stirrup tables (profile stirrup_tables); transfer = the beam carries a new element rising from it
STIRRUP_NOTE = '$12@20'                  # user's correction on the gallery 3-3 (examples: '&12@20'); applied to all gallery ledge beams, UNVERIFIED for 2-2 / 4-4
DOT_D = 1.0                          # dot = closed 2-point polyline with bulge 1 (a circle), diameter 1
BREAK_L = [(0, 10), (0, -13.2), (-6.3, -14.4), (4.9, -17.0), (0, -18.3)]    # break mark offsets from (end x, topping top y); then down to slab bottom (ex 2-2, left end)
MESH_DX0, MESH_STEP, MESH_N = 8.8, 20.0, 3             # topping dots y = H-4: first one 8.8 from the stem face, step 20, 3 per side (ex 2-2)
ST_OVERLAP = {2: 16.0, 3: 13.0}      # stem stirrups = 2 or 3 overlapping rectangles (ex 2-2: 2 x 30 over span 44; ex 5-5: 3 x 35 over span 79)
DIM_OFF = dict(left_near=21.6, left_far=39.7, right_near=21.7, right_far=39.8, bot_near=19.4, bot_far=33.8)   # from the slab end / beam bottom (ex 2-2)

def ndots(span, sp): return max(1, math.ceil(span / sp - 1e-9)) + 1
def lin(a, b, n): return [a + (b - a) * i / (n - 1) for i in range(n)] if n > 1 else [a]

def build(W, H, S, T, sides, S_left=None, S_right=None, solid=None, SD=0.0, drop=0.0, drop_left=0.0, drop_right=0.0):
    """Return dict of primitive lists in beam-left-bottom coordinates. Panel thickness per side (S_left / S_right, default S): the panels are flush on top (stem top = H - T), so a thicker panel
    sits on a LOWER ledge (hl / hr = ledge heights)."""
    ys = H - T; SL, SR = (S_left or S), (S_right or S); ysL, ysR = ys - drop_left, ys - drop_right; hl, hr = ysL - SL, ysR - SR   # drop_left / right (XREF overlay 2026-10-22, UNVERIFIED): that side's panel top is LOWER than the beam top, the stem rises above the slab
    hb = hl if sides == 'left' else hr if sides == 'right' else min(hl, hr)
    left = sides in ('both', 'left'); right = sides in ('both', 'right')
    xs0, xs1 = (LEDGE if left else 0), (W - LEDGE if right else W)
    g = dict(top_l=H - drop_left, top_r=H - drop_right, hb=hb, hbL=hl, hbR=hr, SL=SL, SR=SR, ys=ys, xs0=xs0, xs1=xs1, left=left, right=right, W=W, H=H, S=S, T=T)
    # outline
    c = ([(xs0, H), (xs0, ysL), (xs0, hl), (0, hl), (0, 0)] if left else [(0, H), (0, 0)]) + [(W, 0)] + ([(W, hr), (xs1, hr), (xs1, ysR), (xs1, H)] if right else [(W, H)])
    outline = [c]
    xl, xr = (-SLAB_SHOWN if left else (-SOLID_END if solid == 'left' else 0)), (W + SLAB_SHOWN if right else (W + SOLID_END if solid == 'right' else W))
    yTop = H - drop; yS = yTop - SD
    if solid:      # SOLID (cast) slab on the side that has no ledge: the stem face stops at the slab soffit, soffit line + top line, user's 6-6 geometry
        c = ([(0, yS)] + c[1:]) if solid == 'left' else (c[:-1] + [(W, yS)]); outline = [c]
        outline.append([(0, yS), (xl, yS)] if solid == 'left' else [(W, yS), (xr, yS)])
    if left: outline += [[(0, hl), (xl, hl)], [(xs0, ysL), (xl, ysL)]]
    if right: outline += [[(W, hr), (xr, hr)], [(xs1, ysR), (xr, ysR)]]
    if solid and drop > 0:             # slab top lower than the beam top: beam top line only over the beam + the ledge side, slab top steps down at the face
        tl, tr = (0 if solid == 'left' else xl), (W if solid == 'right' else xr)
        outline.append([(tl, H), (tr, H)]); outline.append([(0, H), (0, yTop), (xl, yTop)] if solid == 'left' else [(W, H), (W, yTop), (xr, yTop)])
    else: outline.append([(xl, H), (xr, H)])
    breaks = []                                              # right break = mirror image of the left one
    if left: breaks.append([(xl + dx, H + dy) for dx, dy in BREAK_L] + [(xl, hl)])
    if right: breaks.append([(xr - dx, H + dy) for dx, dy in BREAK_L] + [(xr, hr)])
    if solid:
        zz = [(x, y * SD / 25.0) if i else (x, y) for i, (x, y) in enumerate(PROF['outline']['zigzag_slab25'])] + [(0, -(SD + PROF['outline']['zigzag_below_slab']))]
        breaks.append([((xl - x) if solid == 'left' else (xr + x), yTop + y) for x, y in zz])
    g.update(outline=outline, breaks=breaks, xl=xl, xr=xr, solid=(dict(side=solid, D=SD, drop=drop, yTop=yTop, yS=yS) if solid else None))
    # slab bar dashes at 3 from slab faces, topping mesh at H-3
    dashed, mesh = [], []
    if left: dashed += [[(xs0, hl + 3), (xl, hl + 3)], [(xs0, ysL - 3), (xl, ysL - 3)]]; mesh.append([(xs0 + 3, H - drop_left - 3), (xl, H - drop_left - 3)])
    if right: dashed += [[(xs1, hr + 3), (xr, hr + 3)], [(xs1, ysR - 3), (xr, ysR - 3)]]; mesh.append([(xs1 - 3, H - drop_right - 3), (xr, H - drop_right - 3)])
    bars = []
    if solid:      # slab bars: continuous rebar layer (57_HATAH_ZIUN), anchored into the stem by ~D (user's hand edit of 3-3 / 4-4, 2026-10-15: 27.9 and 31.8 for D=30; UNVERIFIED: D or the stirrup width)
        anc = min(SD, W - 3); anb = min(60.0, W - 3)      # bottom bar 60 into the beam (user 2026-10-21, 3-3)
        for yy in (yS + 3, yTop - 3):
            a_ = anb if yy == yS + 3 else anc
            bars.append([(a_, yy), (xl, yy)] if solid == 'left' else [(W - a_, yy), (xr, yy)])
    g.update(dashed=dashed, mesh=mesh, bars_solid=bars)
    # help lines (inset 4.5, dash-dot) + stirrup contour (inset 3)
    yl_l, yl_r, yt = hl - INSET_TOPBAR, hr - INSET_TOPBAR, H - INSET_TOPBAR
    bx0, bx1 = INSET_BAR, W - INSET_BAR; sx0, sx1 = xs0 + INSET_BAR, xs1 - INSET_BAR
    help_ = [[(bx0, INSET_BAR), (bx1, INSET_BAR)]]
    if left: help_ += [[(bx0, INSET_BAR), (bx0, yl_l)], [(bx0, hl - 3), (sx0, hl - 3)], [(sx0, yl_l), (sx0, yt)]]
    else: help_ += [[(bx0, INSET_BAR), (bx0, yt)]]
    if right: help_ += [[(bx1, INSET_BAR), (bx1, yl_r)], [(bx1, hr - 3), (sx1, hr - 3)], [(sx1, yl_r), (sx1, yt)]]
    else: help_ += [[(bx1, INSET_BAR), (bx1, yt)]]
    help_.append([(sx0, yt), (sx1, yt)])
    poly = ([(xs1 - 3, H - 3), (xs1 - 3, hr - 3), (W - 3, hr - 3)] if right else [(W - 3, H - 3)]) + [(W - 3, 3), (3, 3)] + ([(3, hl - 3), (xs0 + 3, hl - 3), (xs0 + 3, H - 3)] if left else [(3, H - 3)])
    g.update(help=help_, stirrup_contour=poly)
    # dots
    dots = set(); rows = {}
    nb = ndots(bx1 - bx0, SP_B); bot = [(x, INSET_BAR) for x in lin(bx0, bx1, nb)]; dots.update(bot); rows['bot'] = bot
    nt = ndots(sx1 - sx0, SP_T); top = [(x, yt) for x in lin(sx0, sx1, nt)]; dots.update(top); rows['top'] = top
    for on, xo, xs, yl in ((left, bx0, sx0, yl_l), (right, bx1, sx1, yl_r)):
        if on:
            n1 = ndots(yl - INSET_BAR, SP_V); n2 = ndots(yt - yl, SP_V)
            dots.update((xo, y) for y in lin(INSET_BAR, yl, n1)); dots.update((xs, y) for y in lin(yl, yt, n2))
        else:
            n = ndots(yt - INSET_BAR, SP_FACE); dots.update((xo, y) for y in lin(INSET_BAR, yt, n))
    for on, x0, sg, dd in ((left, xs0, -1, drop_left), (right, xs1, 1, drop_right)):
        if on: dots.update((x0 + sg * (MESH_DX0 + MESH_STEP * k), H - dd - 4) for k in range(MESH_N))
    if solid:
        sgn = -1 if solid == 'left' else 1; xface = 0 if solid == 'left' else W
        dots.add((SOLID_COL if solid == 'left' else W - SOLID_COL, yS + SOLID_SOFFIT_IN))
        for k in range(SOLID_DOT_N):
            for yy in (yTop - SOLID_TOP_IN, yS + SOLID_SOFFIT_IN): dots.add((xface + sgn * (SOLID_DOT0 + SOLID_DOT_STEP * k), yy))
    g.update(dots=sorted(dots), rows=rows)
    # stirrups: lower U's over each ledge, tall overlapping rectangles over the stem; hook ticks at each tall rectangle's top-right corner
    tall = []; span0, span1 = (xs0 + 3 if left else 3), (xs1 - 3 if right else W - 3)
    span = span1 - span0; n, w, _, _ = stirrup_layout(span + 6, STIRRUPS); step = (span - w) / (n - 1) if n > 1 else 0.0     # user's tables 2026-10-15 (stem width = span + 6)
    for i in range(n): tall.append((span0 + i * step, span0 + i * step + w, 3, H - 3))
    ledge_u = []
    if left and right:      # ex 2-2: two 60-wide U's (3..63 open right, 17..77 open left) up to the ledge level hb-3
        ledge_u = [[(63, 3), (3, 3), (3, hl - 3), (63, hl - 3)], [(17, 3), (77, 3), (77, hr - 3), (17, hr - 3)]]
        if W != 80: ledge_u = [[(W * 0.7875, 3), (3, 3), (3, hl - 3), (W * 0.7875, hl - 3)], [(W - W * 0.7875, 3), (W - 3, 3), (W - 3, hr - 3), (W - W * 0.7875, hr - 3)]]
    elif right:             # one ledge: a U across the ledge side, 60 wide (ex 5-5: 60-wide U on the ledge side)
        ledge_u = [[(W - 63, 3), (W - 3, 3), (W - 3, hr - 3), (W - 63, hr - 3)]]
    if left and not right: ledge_u = [[(63, 3), (3, 3), (3, hl - 3), (63, hl - 3)]]
    g.update(tall=tall, ledge_u=ledge_u)
    hooks = []
    for x0, x1, y0, y1 in tall: hooks += [((x1 - 2.9, y1 - 4.3), (x1 - 2.9, y1)), ((x1, y1 - 3.0), (x1 - 4.4, y1 - 3.0))]
    g['hooks'] = hooks
    return g

def add_dot(msp, x, y, layer):
    msp.add_lwpolyline([(x - DOT_D / 2, y, 0, 0, 1), (x + DOT_D / 2, y, 0, 0, 1)], format='xyseb', close=True, dxfattribs=dict(layer=layer, const_width=DOT_D))     # const_width = diameter makes the dot SOLID (user: not hollow; examples use width 1.0)


DET_TOP, DET_STAGGER, DET_TXT_DY = -74.5, 5.9, 19.8            # first tall stirrup's top is 74.5 below the beam bottom; 2nd is 5.9 lower; text 19.8 under the lowest edge (user's 3-3)
DET_U_Y0, DET_U_LEFT_X1, DET_U_RIGHT_DX = -113.3, -19.1, 13.3   # U details: top edge y; left U's right end x; right U starts 13.3 right of the beam face
HOOK_DX, HOOK_DY1, HOOK_DY2, HOOK_DX2 = 2.8, 4.3, 2.7, 4.5      # hook ticks at a stirrup's top-right corner (user's detail)
STIRRUP_U_NOTE = '$12@15'                                        # ledge U stirrups (user's 3-3): always the standard note
STIRRUP_SPACING = '$12@15'                                       # detail notes (user's 3-3); the section note says $12@20

OVERLAY = False                  # user 2026-10-22: sections over a Revit XREF - the XREF already shows the concrete outline, slab breaks and dimensions: draw ONLY the reinforcement (bars, stirrups, leaders, notes, stirrup details)
SOLID_SYM = None                 # user 2026-10-18: solid slab with NO thickness on the plan -> its thickness dimension carries the symbol 'H' (drawn at --solid-D)
H_SYM = None                     # untagged beam (user 2026-10-15): the height is the PARAMETER h - height dimensions carry the symbol ('h', 'h-6', 'h-25') instead of a number, no L= lengths
BARZEL_STYLE = 'dim_25_BARZEL'   # steel-bar style: text only (no dim line, arrows or extension lines) written ON the bar (user's final rule, round 4: ALL detail dims)

def dim_w_barzel(msp, P, x0, x1, y_edge, layer):
    """Width of a bar written ON its horizontal edge (text above the edge): U stirrups on their top edge, tall stirrups on their bottom edge (user's 3-3)."""
    msp.add_linear_dim(base=P((x0, y_edge)), p1=P((x0, y_edge)), p2=P((x1, y_edge)), angle=0, dimstyle=BARZEL_STYLE, dxfattribs={'layer': layer}).render()

def dim_leg_barzel(msp, P, x, y0, y1, side, layer, text=None):
    """Length of a vertical bar leg written ON the leg (style dim_25_BARZEL, aligned, no arrows). side='east'/'west' = which side the text sits (outside of a closed edge)."""
    a, b = ((x, y1), (x, y0)) if side == 'east' else ((x, y0), (x, y1))      # the text goes to the left of the direction of measurement
    kw = dict(p1=P(a), p2=P(b), distance=0, dimstyle=BARZEL_STYLE, dxfattribs={'layer': layer}); kw.update({'text': text} if text else {}); msp.add_aligned_dim(**kw).render()

def draw_details(doc, tmpl, ox, oy, tall, U_left, U_right, H, hbL, hbR, W, dims_only=False):
    """Stirrup detail row under a ledge-beam section (user's 3-3): tall stirrups (staggered rectangles), U stirrups for the ledges, each with dims and note.
    dims_only: redraw only the dimensions (used to restyle a hand-edited cell without touching the user's other items)."""
    msp = doc.modelspace(); L = PROF['layers']; P = lambda p: (ox + p[0], oy + p[1]); D_ = PROF['dim']
    def poly(pts, close=False):
        if not dims_only: msp.add_lwpolyline([P(p) for p in pts], close=close, dxfattribs=dict(layer='57_HATAH_ZIUN'))
    def line(a, b):
        if not dims_only: msp.add_line(P(a), P(b), dxfattribs=dict(layer='57_HATAH_ZIUN'))
    def dim(base, p1, p2, ang): msp.add_linear_dim(base=P(base), p1=P(p1), p2=P(p2), angle=ang, dimstyle=D_['style'], override=D_['override'], dxfattribs={'layer': L['text']}).render()
    def txt(raw, x, y):
        if dims_only: return
        a = dict(tmpl['stirrup']); a.update(layer=L['text'], insert=P((x, y))); msp.add_text(raw, height=a.pop('height'), dxfattribs=a)
    h = H - 6; n = len(tall); w = tall[0][1] - tall[0][0]
    for i, (x0, x1, _, _) in enumerate(tall):
        yt = DET_TOP - DET_STAGGER * i; yb = yt - h
        poly([(x1, yt), (x0, yt), (x0, yb), (x1, yb)], close=True)
        line((x1 - HOOK_DX, yt - HOOK_DY1), (x1 - HOOK_DX, yt)); line((x1, yt - HOOK_DY2), (x1 - HOOK_DX2, yt - HOOK_DY2))
        dim_w_barzel(msp, P, x0, x1, yb, L['text']); dim_leg_barzel(msp, P, x1, yb, yt, 'west', L['text'], f'{H_SYM}-6' if H_SYM else None)
    ylow = DET_TOP - DET_STAGGER * (n - 1) - h
    txt(f"{n if n > 1 else ''}{STIRRUP_SPACING}{'' if H_SYM else f' L={round(2 * (w + h) + 12)}'}", tall[0][0] - 6.7, ylow - DET_TXT_DY)
    y0 = DET_U_Y0
    if U_left:
        uh = hbL - 6; LU = round(60 + 2 * uh + 26); y1 = y0 - uh; x1 = DET_U_LEFT_X1; x0 = x1 - 60
        poly([(x1, y1), (x0, y1), (x0, y0), (x1, y0)]); dim_w_barzel(msp, P, x0, x1, y0, L['text']); dim_leg_barzel(msp, P, x0, y1, y0, 'west', L['text'], f'{H_SYM}-{H - hbL + 6:g}' if H_SYM else None)
        txt(f"{STIRRUP_U_NOTE}{'' if H_SYM else f' L={LU}'}", x0 + 2.7, y1 - 12.0)
    if U_right:
        uh = hbR - 6; LU = round(60 + 2 * uh + 26); y1 = y0 - uh; x0 = W + DET_U_RIGHT_DX; x1 = x0 + 60
        poly([(x0, y1), (x1, y1), (x1, y0), (x0, y0)]); dim_w_barzel(msp, P, x0, x1, y0, L['text']); dim_leg_barzel(msp, P, x1, y1, y0, 'east', L['text'], f'{H_SYM}-{H - hbR + 6:g}' if H_SYM else None)
        txt(f"{STIRRUP_U_NOTE}{'' if H_SYM else f' L={LU}'}", x0 + 4.3, y1 - 12.0)

def draw(doc, g, ox, oy, name, tmpl):
    """Write the section into modelspace with the beam's bottom-left at (ox, oy). Returns the written bbox."""
    msp = doc.modelspace(); L = PROF['layers']; P = lambda p: (ox + p[0], oy + p[1])
    def poly(pts, layer, close=False, lt=None):
        at = dict(layer=layer); at.update(dict(linetype=lt) if lt else {})
        return msp.add_lwpolyline([P(p) for p in pts], close=close, dxfattribs=at)
    def line(a, b, layer): msp.add_line(P(a), P(b), dxfattribs=dict(layer=layer))
    if not OVERLAY:
        for p in g['outline']: poly(p, L['break'], lt='Continuous')
        for p in g['breaks']: poly(p, L['break'], lt='Continuous')
    for p in g['dashed']: poly(p, '51_HATAH_DASHED')
    for p in g['mesh']: poly(p, '57_HATAH_ZIUN')
    for p in g.get('bars_solid', []): poly(p, '57_HATAH_ZIUN')
    for a in g['help']: line(a[0], a[1], '2000_DOT_HELP_LINE')
    poly(g['stirrup_contour'], '2000_DOT_HELP_LINE', close=True)
    for x, y in g['dots']: add_dot(msp, ox + x, oy + y, '57_HATAH_ZIUN')
    for x0, x1, y0, y1 in g['tall']: poly([(x1, y1), (x0, y1), (x0, y0), (x1, y0)], '57_HATAH_ZIUN', close=True)
    for u in g['ledge_u']: poly(u, '57_HATAH_ZIUN')
    for a, b in g['hooks']: line(a, b, '57_HATAH_ZIUN')
    W, H, hb, S, T = g['W'], g['H'], g['hb'], g['S'], g['T']
    # leaders (layer 56_HATAH_ZET) + notes (54_HATAH_TEXT); offsets in beam coordinates measured on ex 2-2
    def txt(raw, key, x, y, **kw):
        a = dict(tmpl[key]); a.update(layer=L['text'], insert=P((x, y))); a.update(kw)
        msp.add_text(raw, height=a.pop('height'), dxfattribs=a)
    bot, top = g['rows']['bot'], g['rows']['top']; n = len(bot)
    yb = hb * 0.556
    # stirrup note: underline in the free space below a slab (both sides: under the left slab as ex 2-2; one side: beside the beam on the slab's side), fork to the outer legs
    if g['left'] and g['right']: ex, ux0, tx = -16.8, -44.6, -43.2
    elif g['right']: ex, ux0, tx = W + 16.8, W + 44.6, W + 18.2
    else: ex, ux0, tx = -16.8, -44.6, -43.2
    both = g['left'] and g['right']; yl_, yr_ = (20.0, 20.0) if both else (23.2, 20.0)      # user's corrected fork ends (3-3 / 2-2 / 4-4)
    poly([(ux0, 12.7), (ex, 12.7)], '56_HATAH_ZET'); line((ex, 12.7), (INSET_BAR, yl_), '56_HATAH_ZET'); line((ex, 12.7), (W - INSET_BAR, yr_), '56_HATAH_ZET')
    txt(STIRRUP_NOTE, 'stirrup', tx, 14.2)
    # bottom bars 'per plan': fork to two bottom dots, elbow below the beam, text right of it
    i1, i2 = max(0, n // 2 - 1), n - 2; ex = W - 8.8
    for i in (i1, i2): line(bot[i], (ex, -10.0), '56_HATAH_ZET')
    poly([(ex, -10.0), (W + 53.7, -10.0)], '56_HATAH_ZET'); txt('c/,/ kph ,fbh,', 'bt', W + 50.5, -8.4)
    # top bars 'per plan' of the stem: fork to two top dots. Both slab sides: elbow raised above the mesh notes, text right (user's 3-3 correction).
    # One slab side: on the free plain side (user's 4-4 correction: left of the stem, elbow 12.5 right of the first top dot, 14 above the topping).
    nt = len(top); j1, j2 = max(0, nt // 2 - 1), nt - 1
    solid = g.get('solid'); two_vis = (g['left'] and g['right']) or bool(solid)
    if two_vis:
        ex, ey = g['xs1'] - 1.2, H + 25.2
        for j in (j1, j2): line(top[j], (ex, ey), '56_HATAH_ZET')
        poly([(ex, ey), (ex + 61.4, ey)], '56_HATAH_ZET'); txt('c/g/ kph ,fbh,', 'tp', ex + 58.2, ey + 2.8)
    else:
        sg = -1 if g['right'] else 1                                    # note goes to the plain side
        ex, ey = (top[0][0] + 8.0) if g['right'] else (top[-1][0] - 8.0), H + 14.0
        for j in (j1, j2): line(top[j], (ex, ey), '56_HATAH_ZET')
        poly([(ex, ey), (ex + sg * 61.4, ey)], '56_HATAH_ZET'); txt('c/g/ kph ,fbh,', 'tp', ex - 4.8 if g['right'] else ex + 4.8, ey + 2.8)
    # topping mesh 'zhui per plan' (reinforcement per plan) leaders. Both sides: from the dot nearest the stem; one side: from the SECOND dot, longer (user's corrections)
    for on, x0, sg in ((g['left'], g['xs0'], -1), (g['right'], g['xs1'], 1)):
        if on:
            two = two_vis; k0 = 0 if two else 1
            xd = x0 + sg * (MESH_DX0 + MESH_STEP * k0); tsd = g.get('top_l', H) if sg < 0 else g.get('top_r', H)
            if two: ye, ex_, xe = (tsd + 16.4 if sg < 0 else tsd + 13.6), xd + sg * 4.7, xd + sg * (57.5 if sg < 0 else 61.2)
            else: ye, ex_, xe = tsd + 16.4, xd + sg * 11.4, xd + sg * 68.3
            poly([(xd, tsd - 4), (ex_, ye), (xe, ye)], '56_HATAH_ZET')
            tx, ty = (xd + 0.1, tsd + 18.6) if (two and sg < 0) else (xe + sg * (2.1 if two else 0.9), ye + (1.1 if two else 1.4))
            txt(' zhui kph ,fbh,' if two else 'zhui  kph ,fbh,', 'pp', tx, ty)
    # dimensions (dim_25 on 53_HATAH_MIDA), offsets as on ex 2-2
    D = PROF['dim']
    def dim(base, p1, p2, ang, text=None):
        if OVERLAY: return
        kw = dict(base=P(base), p1=P(p1), p2=P(p2), angle=ang, dimstyle=D['style'], override=D['override'], dxfattribs={'layer': L['dim']}); kw.update({'text': text} if text else {}); msp.add_linear_dim(**kw).render()
    xl, xr = g['xl'], g['xr']
    parts = ([(0, g['xs0'])] if g['left'] else []) + [(g['xs0'], g['xs1'])] + ([(g['xs1'], W)] if g['right'] else [])
    for a, b in parts:
        if b - a > 0.3: dim((a, -DIM_OFF['bot_near']), (a, 0), (b, 0), 0)
    dim((0, -DIM_OFF['bot_far']), (0, 0), (W, 0), 0)
    if g['right']:
        for i, (a, b) in enumerate(((0, g['hbR']), (g['hbR'], g['hbR'] + g['SR']), (g['hbR'] + g['SR'], H))): dim((xr + DIM_OFF['right_near'], a), (g['xs1'], a), (g['xs1'], b), 90, f"{H_SYM}-{H - g['hbR']:g}" if (H_SYM and i == 0) else None)
        dim((xr + DIM_OFF['right_far'], 0), (W, 0), (W, H), 90, H_SYM)
    if g['left']:
        for i, (a, b) in enumerate(((0, g['hbL']), (g['hbL'], g['hbL'] + g['SL']), (g['hbL'] + g['SL'], H))): dim((xl - DIM_OFF['left_near'], a), (0, a), (0, b), 90, f"{H_SYM}-{H - g['hbL']:g}" if (H_SYM and i == 0) else None)
    if not g['right'] and g['left']: dim((xl - DIM_OFF['left_far'], 0), (0, 0), (0, H), 90, H_SYM)     # overall height once, on the slab side
    if solid:      # notes + dims of the solid slab, offsets measured on the user's 6-6 (general_beam.py)
        yT, yS_, y2 = solid['yTop'], solid['yS'], solid['yS'] + SOLID_SOFFIT_IN
        z = '56_HATAH_ZET'
        if solid['side'] == 'right':
            ex, ey = W + 28.8, yT + 5.6; line((W + 10.5, yT - SOLID_TOP_IN), (ex, ey), z); line((W + 21.9, yT - 3), (ex, ey), z); line((ex, ey), (ex + 45.3, ey), z); txt('c/g/ kph ,fw', 'tp_cast', ex + 43.9, ey + 1.5)
            ex, ey = W + 19.8, y2 - 16.7; line((W + 15.6, yS_ + 3), (ex, ey), z); line((W + 9.9, y2), (ex, ey), z); line((ex, ey), (ex + 45.0, ey), z); txt('c/,/ kph ,fw', 'bt_cast', ex + 44.4, ey + 1.2)
            for y0_, y1_ in ((0, yS_), (yS_, yT), (yT, H)):             # chain below slab / slab / above slab on the slab side (gallery blocks 1, 13, 16: each side carries its own chain)
                if y1_ - y0_ > 0.3: dim((xr + DIM_OFF['right_near'], y0_), (W, y0_), (W, y1_), 90, SOLID_SYM if (SOLID_SYM and y0_ == yS_) else None)
        else:
            line((-10.6, yT - SOLID_TOP_IN), (-28.9, yT + 7.1), z); line((-28.9, yT + 7.1), (-74.2, yT + 7.1), z); txt('c/g/ kph ,fw', 'tp_cast', -30.3, yT + 8.5)
            line((-10.0, y2), (-18.0, y2 - 19.4), z); line((-18.0, y2 - 19.4), (-63.0, y2 - 19.4), z); txt('c/,/ kph ,fw', 'bt_cast', -19.6, y2 - 18.7)
            for y0_, y1_ in ((0, yS_), (yS_, yT), (yT, H)):
                if y1_ - y0_ > 0.3: dim((xl - DIM_OFF['left_near'], y0_), (0, y0_), (0, y1_), 90, SOLID_SYM if (SOLID_SYM and y0_ == yS_) else None)
    draw_details(doc, tmpl, ox, oy, g['tall'], g['left'], g['right'], H, g['hbL'], g['hbR'], W)
    return (xl, 0, xr, H)


# ---------------------------------------------------------------- cast edge beam + slab on one side (ground-floor example 1-1: generic B / D / H detail)
CAST_COL_L, CAST_COL_R, CAST_TOP, CAST_BOT2 = 4.4, 4.3, 4.3, 4.4     # dot column insets (left/right face), top dots from the top, slab-soffit-level dots above the soffit (ex 1-1)
CORE_LAYER = '10_PLADA_HATAH'


def core_row(x0, sg, H, D, T):
    """Hollow-core OPENINGS of a slab of thickness D (panel p = D - T) beside the stem face x0, sg = +1 right / -1 left, as OBROUNDS (user 2026-10-21: "mark the openings in the hollow-core slabs as
    obround"; his sample on 5-5 = 21 wide x 31.5 high stadium, layer 10_PLADA_HATAH, for p = 40 -> scaled by p / 40). Returns [(cx, cy, W, Hh)]: centre in the panel (soffit + p/2 + 0.8),
    first centre >= 8.3 (and W/2 + 3.3) from the face, pitch >= 20 (and W + 3), up to 3 that fit inside the slab end (58.9)."""
    p = D - T; k = p / 40.0; W, Hh = 16.8 * k, 25.2 * k; first = max(8.3, W / 2 + 3.3); pitch = max(20.0, W + 3); cy = H - D + p / 2 + 0.8
    n = max(1, min(3, int((CAST_SLAB_END - 1.5 - W / 2 - first) // pitch) + 1))
    return [(x0 + sg * (first + pitch * j), cy, W, Hh) for j in range(n)]


def obround(msp, cx, cy, W, Hh, layer, P=lambda q: q):
    """closed stadium polyline (vertical, semicircle ends), width W, height Hh, centre (cx, cy)"""
    r, L = W / 2, Hh / 2 - W / 2
    pts = [(cx + r, cy - L, 0), (cx + r, cy + L, 1), (cx - r, cy + L, 0), (cx - r, cy - L, 1)]
    return msp.add_lwpolyline([(*P((x, y)), 0, 0, bg) for x, y, bg in pts], format='xyseb', close=True, dxfattribs=dict(layer=layer))


CAST_SLAB_END, CAST_SLAB_DOT0, CAST_SLAB_STEP, CAST_VSTEP = 58.9, 9.9, 15.0, 20.0   # slab shown beyond the stem face; first slab dot from the stem face; steps (ex 1-1)

def draw_stem_stirrups(msp, P, B, H, n, w, layer='57_HATAH_ZIUN', closed_top=True):
    """stirrups INSIDE a cast / general beam section: the user's table gives n stirrups of width w for this thickness (red clouds on 12-12 and 8-8, 2026-10-16: the section must show the overlapping
    rectangles, not one B-6 wide stirrup). n = 1: the old single closed rectangle B-6 x H-6 with its hook; n > 1: n rectangles (x0, x0 + w, 3, H-3), step (B-6-w)/(n-1), hook ticks at each top-right corner (as the ledge sections' tall stirrups)."""
    line = lambda a, b: msp.add_line(P(a), P(b), dxfattribs=dict(layer=layer))
    if n <= 1:
        msp.add_lwpolyline([P(p) for p in [(3, H - 3), (3, 3), (B - 3, 3), (B - 3, H - 3)]], close=False, dxfattribs=dict(layer=layer))
        if closed_top: line((3, H - 3), (B - 3, H - 3))
        line((B - 5.8, H - 7.3), (B - 5.8, H - 3)); line((B - 3, H - 5.7), (B - 7.5, H - 5.7)); return
    st = (B - 6 - w) / (n - 1)
    for i in range(n):
        x0, x1 = 3 + i * st, 3 + i * st + w
        msp.add_lwpolyline([P(p) for p in [(x1, H - 3), (x0, H - 3), (x0, 3), (x1, 3)]], close=True, dxfattribs=dict(layer=layer))
        line((x1 - 2.9, H - 3 - 4.3), (x1 - 2.9, H - 3)); line((x1, H - 3 - 3.0), (x1 - 4.4, H - 3 - 3.0))

def build_cast(B, H, D, T=5.0, both=False, D_left=None, none=False, solid_D=0.0):
    """Cast beam beside hollow-core panels that RUN PAST it (cores as circles). D = slab thickness (panel + topping T) on the right; both=True adds the mirror slab on the left (thickness D_left)."""
    if none:                                           # free beam, no slab beside it: rectangle B x H, two columns of bars (step <= 20), no slab notes
        xl, xr, yt = CAST_COL_L, B - CAST_COL_R, H - CAST_TOP; n = max(1, math.ceil((yt - INSET_BAR) / CAST_VSTEP - 1e-9)) + 1; col_y = lin(INSET_BAR, yt, n)
        return dict(B=B, H=H, D=0, DL=0, T=T, both=False, none=True, y2=col_y[-2] if n > 2 else yt, yt=yt, xl=xl, xr=xr, end=B, endL=0.0, col_y=col_y, dots=sorted({(x, y) for x in (xl, xr) for y in col_y}), mid_y=col_y[1:-1], cores=[])
    DL = D_left or D; Dmax = max(D, DL) if both else D
    y2, yt = H - Dmax + CAST_BOT2, H - CAST_TOP; xl, xr = CAST_COL_L, B - CAST_COL_R; end = B + CAST_SLAB_END; endL = -CAST_SLAB_END if (both or solid_D) else 0.0
    n = max(1, math.ceil((y2 - INSET_BAR) / CAST_VSTEP - 1e-9)) + 1
    col_y = lin(INSET_BAR, y2, n) + [yt]
    dots = [(x, y) for x in (xl, xr) for y in col_y] + [(B + 7.4 + 20.0 * k, H - 4) for k in range(2)]     # user's 1-1: 2 topping mesh dots, no slab dot rows
    cores = core_row(B, 1, H, D, T)                                                                         # 3 cores r=5, 20 apart (user's 1-1); thicker panel -> bigger cores
    if solid_D:      # SOLID slab on the side opposite the hollow-core one (user 2026-10-18, 7-7: 'casting completion'); dot rows as the solid slab of the ledge sections
        dots += [(-(SOLID_DOT0 + SOLID_DOT_STEP * k), yy) for k in range(SOLID_DOT_N) for yy in (H - SOLID_TOP_IN, H - solid_D + SOLID_SOFFIT_IN)]
    if both:
        dots += [(-7.4 - 20.0 * k, H - 4) for k in range(2)]; cores += core_row(0, -1, H, DL, T)
    return dict(solid=(dict(SD=solid_D, yS=H - solid_D) if solid_D else None), B=B, H=H, D=D, DL=DL, T=T, both=both, none=False, y2=y2, yt=yt, xl=xl, xr=xr, end=end, endL=endL, col_y=col_y, dots=sorted(set(dots)), mid_y=col_y[1:-2], cores=cores)

def draw_free_beam(doc, g, ox, oy, tmpl):
    """Free (cast) beam, no slab beside it: outline, stirrup B-6 x H-6 with hook, two bar columns, `2$12` top pair, `2$12` bottom pair, stirrup note, dims B and H, stirrup detail below.
    Rules copied from the user's cast sections; there is no example of a slab-less beam: UNVERIFIED (flagged in the report of recipes/plan_sections.py)."""
    msp = doc.modelspace(); L = PROF['layers']; P = lambda p: (ox + p[0], oy + p[1]); B, H = g['B'], g['H']; xl, xr, yt = g['xl'], g['xr'], g['yt']
    line = lambda a, b, lay: msp.add_line(P(a), P(b), dxfattribs=dict(layer=lay))
    poly = lambda pts, lay, close=False: msp.add_lwpolyline([P(p) for p in pts], close=close, dxfattribs=dict(layer=lay))
    for a, b in (((0, H), (0, 0)), ((0, 0), (B, 0)), ((B, 0), (B, H)), ((0, H), (B, H))): line(a, b, L['outline_new'])
    poly([(3, H - 3), (3, 3), (B - 3, 3), (B - 3, H - 3)], '57_HATAH_ZIUN'); line((3, H - 3), (B - 3, H - 3), '57_HATAH_ZIUN')
    line((B - 5.8, H - 7.3), (B - 5.8, H - 3), '57_HATAH_ZIUN'); line((B - 3, H - 5.7), (B - 7.5, H - 5.7), '57_HATAH_ZIUN')
    for x, y in g['dots']: add_dot(msp, ox + x, oy + y, '57_HATAH_ZIUN')
    def txt(raw, key, x, y):
        a = dict(tmpl[key]); a.update(layer=L['text'], insert=P((x, y))); msp.add_text(raw, height=a.pop('height'), dxfattribs=a)
    z = '56_HATAH_ZET'
    ex, ey = -3.9, H + 10
    for x, y in ((xr, yt), (xl, yt)): line((ex, ey), (x, y), z)
    poly([(ex, ey), (ex - 20.7, ey)], z); txt('2$12', 'c2', ex - 19.9, ey + 1.0)
    ex, ey = B + 4.5, -5.6
    line((ex, ey), (xl, INSET_BAR), z); line((ex, ey), (xr, INSET_BAR), z); poly([(ex, ey), (ex + 20.6, ey)], z); txt('2$12', 'c2', ex + 1.9, ey + 1.0)
    my = g['mid_y'][len(g['mid_y']) // 2] if g['mid_y'] else H / 2; ex, ey = B + 4.0, my - 8.0
    line((xl, my), (ex, ey), z); line((xr, my), (ex, ey), z); poly([(ex, ey), (ex + 27.8, ey)], z); txt(STIRRUP_NOTE, 'stirrup', ex + 1.4, ey + 1.5)
    D_ = PROF['dim']
    def dim(base, p1, p2, ang, lay=L['dim']): msp.add_linear_dim(base=P(base), p1=P(p1), p2=P(p2), angle=ang, dimstyle=D_['style'], override=D_['override'], dxfattribs={'layer': lay}).render()
    dim((0, -18.2), (0, 0), (B, 0), 0); dim((B + 30, 0), (B, 0), (B, H), 90)
    h = H - 6; x0, x1 = 3, B - 3; yt_, yb_ = DET_TOP, DET_TOP - h
    poly([(x1, yt_), (x0, yt_), (x0, yb_), (x1, yb_)], '57_HATAH_ZIUN', close=True)
    line((x1 - HOOK_DX, yt_ - HOOK_DY1), (x1 - HOOK_DX, yt_), '57_HATAH_ZIUN'); line((x1, yt_ - HOOK_DY2), (x1 - HOOK_DX2, yt_ - HOOK_DY2), '57_HATAH_ZIUN')
    dim_w_barzel(msp, P, x0, x1, yb_, L['text']); dim_leg_barzel(msp, P, x1, yb_, yt_, 'east', L['text'])
    txt(f"{STIRRUP_SPACING} L={round(2 * ((x1 - x0) + h) + 12)}", 'stirrup', x0 - 6.7, yb_ - DET_TXT_DY)

def draw_cast(doc, g, ox, oy, tmpl, mirror=False):
    """mirror=True: the same section seen from the other side (slab on the LEFT, e.g. a south edge beam viewed E). Geometry x -> B - x; a note keeps its reading direction, so its text stays at the same end offset of the (mirrored) underline."""
    msp = doc.modelspace(); L = PROF['layers']; B, H, D, DL, T, end, endL, both = g['B'], g['H'], g['D'], g['DL'], g['T'], g['end'], g['endL'], g['both']
    P = (lambda p: (ox + B - p[0], oy + p[1])) if mirror else (lambda p: (ox + p[0], oy + p[1]))
    line = lambda a, b, lay: msp.add_line(P(a), P(b), dxfattribs=dict(layer=lay))
    poly = lambda pts, lay, close=False: msp.add_lwpolyline([P(p) for p in pts], close=close, dxfattribs=dict(layer=lay))
    if g.get('none'): return draw_free_beam(doc, g, ox, oy, tmpl)
    sol = g.get('solid')
    segs = [((0, H - DL) if both else ((0, sol['yS']) if sol else (0, H)), (0, 0)), ((0, 0), (B, 0)), ((B, 0), (B, H - D)), ((B, H - D), (end, H - D)), ((endL, H), (end, H))]
    if both: segs.append(((0, H - DL), (endL, H - DL)))
    if sol: segs.append(((0, sol['yS']), (endL, sol['yS'])))
    for a, b in segs: line(a, b, L['outline_new'])
    zig = lambda dd: [(x, y * dd / 25.0) if i else (x, y) for i, (x, y) in enumerate(PROF['outline']['zigzag_slab25'])] + [(0, -(dd + PROF['outline']['zigzag_below_slab']))]
    poly([(end + x, H + y) for x, y in zig(D)], L['break'])
    if both: poly([(endL - x, H + y) for x, y in zig(DL)], L['break'])
    if sol: poly([(endL - x, H + y) for x, y in zig(sol['SD'])], L['break'])
    line((end, H - T), (B - 3, H - T), L['break'])                                                          # topping soffit line (user's 1-1)
    if both: line((endL, H - T), (3, H - T), L['break'])
    for cx, cy, cw, ch in g['cores']: obround(msp, cx, cy, cw, ch, CORE_LAYER, P)        # hollow cores
    line((B - 3, H - 3), (end, H - 3), '57_HATAH_ZIUN')                                                     # topping mesh line
    if both: line((3, H - 3), (endL, H - 3), '57_HATAH_ZIUN')
    n_s, w_s, _, _ = stirrup_layout(B, STIRRUPS); draw_stem_stirrups(msp, P, B, H, n_s, w_s)          # the table's stirrups inside the section (standard 65 -> 2 x 40)
    if sol:          # slab bars on the continuous rebar layer, anchored into the stem by ~D (as the ledge sections' solid slab)
        anc = min(sol['SD'], B - 3)
        for yy in (sol['yS'] + 3, H - 3): line((min(60.0, B - 3) if yy == sol['yS'] + 3 else anc, yy), (endL, yy), '57_HATAH_ZIUN')      # bottom bar 60 into the beam (user 2026-10-21)
    for x, y in g['dots']: add_dot(msp, *P((x, y)), '57_HATAH_ZIUN')
    def txt(raw, key, x, y, span=None):
        a = dict(tmpl[key])
        if mirror and span:      # span = the note's underline (xa, xb) in unmirrored coordinates; flag-2 text hangs from the right end, others from the left end
            xa, xb = span; x = (B - xa) - (xb - x) if a.get('text_generation_flag', 0) & 2 else (B - xb) + (x - xa); a.update(layer=L['text'], insert=(ox + x, oy + y))
        else: a.update(layer=L['text'], insert=P((x, y)))
        msp.add_text(raw, height=a.pop('height'), dxfattribs=a)
    z = '56_HATAH_ZET'; xl, xr, y2, yt = g['xl'], g['xr'], g['y2'], g['yt']
    ex, ey = (B / 2 - 3.9, H + 30) if (both or sol) else (-3.9, H + 10)        # 4$12: forks to the top pair (user's 1-1); above the beam when slabs are on both sides
    for x, y in ((xr, yt), (xl, yt)): line((ex, ey), (x, y), z)
    if both or sol: poly([(ex, ey), (ex + 20.7, ey)], z); txt('4$12', 'c4', ex + 0.8, ey + 1.0, (ex, ex + 20.7))
    else: poly([(ex, ey), (ex - 20.7, ey)], z); txt('4$12', 'c4', ex - 19.9, ey + 1.0, (ex - 20.7, ex))
    ex, ey = B + 4.5, -5.6                                                     # 2$12 bottom pair
    line((ex, ey), (xl, INSET_BAR), z); line((ex, ey), (xr, INSET_BAR), z); poly([(ex, ey), (ex + 20.6, ey)], z); txt('2$12', 'c2', ex + 1.9, ey + 1.0, (ex, ex + 20.6))
    my = g['mid_y'][0] if g['mid_y'] else (INSET_BAR + y2) / 2                  # stirrup note: both forks converge on one elbow right of the stem (user's 1-1)
    ex, ey = B + 4.0, 16.0
    line((xl, my), (ex, ey), z); line((xr, my), (ex, ey), z); poly([(ex, ey), (ex + 27.8, ey)], z); txt(STIRRUP_NOTE, 'stirrup', ex + 1.4, ey + 1.5, (ex, ex + 27.8))
    ex, ey = B + 45.8, H + 16.5                                                # slab top bars per plan: fork to the mesh line and the 2nd mesh dot
    line((ex, ey), (B + 35.6, H - 3), z); line((ex, ey), (B + 27.4, H - 4), z); poly([(ex, ey), (ex + 45.4, ey)], z); txt('c/g/ kph ,fw', 'tp_cast', ex + 43.9, ey + 1.4, (ex, ex + 45.4))
    if both:                                                                   # mirrored note on the left slab (mirrored text runs leftwards from its insert point)
        ex = -45.8
        line((ex, ey), (-35.6, H - 3), z); line((ex, ey), (-27.4, H - 4), z); poly([(ex, ey), (ex - 45.4, ey)], z); txt('c/g/ kph ,fw', 'tp_cast', ex - 1.5, ey + 1.4, (ex - 45.4, ex))
    if sol:          # notes of the solid slab (offsets measured on the user's 6-6, left variant)
        yT, yS_ = H, sol['yS']; y2s = yS_ + SOLID_SOFFIT_IN
        line((-10.6, yT - SOLID_TOP_IN), (-28.9, yT + 7.1), z); poly([(-28.9, yT + 7.1), (-74.2, yT + 7.1)], z); txt('c/g/ kph ,fw', 'tp_cast', -30.3, yT + 8.5, (-74.2, -28.9))
        line((-10.0, y2s), (-18.0, y2s - 19.4), z); poly([(-18.0, y2s - 19.4), (-63.0, y2s - 19.4)], z); txt('c/,/ kph ,fw', 'bt_cast', -19.6, y2s - 18.7, (-63.0, -18.0))
    D_ = PROF['dim']
    def dim(base, p1, p2, ang, lay=L['dim'], text=None):
        kw = dict(base=P(base), p1=P(p1), p2=P(p2), angle=ang, dimstyle=D_['style'], override=D_['override'], dxfattribs={'layer': lay}); kw.update({'text': text} if text else {}); msp.add_linear_dim(**kw).render()
    dim((0, -18.2), (0, 0), (B, 0), 0)
    if sol:
        for y0_, y1_ in ((0, sol['yS']), (sol['yS'], H)):
            if y1_ - y0_ > 0.3: dim((endL - 21.6, y0_), (0, y0_), (0, y1_), 90, text=(SOLID_SYM if (SOLID_SYM and y0_ == sol['yS']) else None))
    dim((end + 16.7, H - D), (end, H - D), (end, H), 90); dim((end + 29.9, 0), (B, 0), (B, H), 90)
    if both: dim((endL - 16.7, H - DL), (endL, H - DL), (endL, H), 90)
    # stirrup detail under the section: the user's tables give n stirrups of width w for this beam thickness (n = 1: one rectangle B-6 x H-6 with hook, dims and note)
    n_, w_, _, _ = stirrup_layout(B, STIRRUPS)
    if n_ > 1:
        st_ = (B - 6 - w_) / (n_ - 1); draw_details(doc, tmpl, ox, oy, [(3 + i * st_, 3 + i * st_ + w_, 3, H - 3) for i in range(n_)], False, False, H, 0, 0, B); return
    h = H - 6; x0, x1 = 3, B - 3; yt_, yb_ = DET_TOP, DET_TOP - h
    poly([(x1, yt_), (x0, yt_), (x0, yb_), (x1, yb_)], '57_HATAH_ZIUN', close=True)
    line((x1 - HOOK_DX, yt_ - HOOK_DY1), (x1 - HOOK_DX, yt_), '57_HATAH_ZIUN'); line((x1, yt_ - HOOK_DY2), (x1 - HOOK_DX2, yt_ - HOOK_DY2), '57_HATAH_ZIUN')
    dim_w_barzel(msp, P, x0, x1, yb_, L['text']); dim_leg_barzel(msp, P, x1, yb_, yt_, 'west' if mirror else 'east', L['text'])
    txt(f"{STIRRUP_SPACING} L={round(2 * ((x1 - x0) + h) + 12)}", 'stirrup', x0 - 6.7, yb_ - DET_TXT_DY, (0, B))      # centred under the symmetric stirrup: same physical x when mirrored

def template_texts(doc):
    """Copy style/height/width of the example's note texts (found by their raw text inside the profile's examples_box) so new notes match."""
    ex0, ey0, ex1, ey1 = PROF.get('examples_box', [0, 0, 1e12, 1e12])
    want = {'stirrup': '&12@20', 'bt': 'c/,/ kph ,fbh,', 'tp': 'c/g/ kph ,fbh,', 'pp': ' kph ,fbh,'}
    want_cast = {'c4': '4&12', 'c2': '2&12', 'c28': '2&8@20', 'st': '&10@15', 'bt_cast': 'c/,/ kph ,fw', 'tp_cast': 'c/g/ kph ,fw'}
    out = {}
    for e in doc.modelspace().query('TEXT'):
        if not (ex0 < e.dxf.insert.x < ex1 and ey0 < e.dxf.insert.y < ey1): continue
        for k, raw in {**want, **want_cast}.items():
            if e.dxf.text == raw and k not in out:
                d = e.dxf; out[k] = dict(style=d.style, height=d.height, width=d.get('width', 1.0), text_generation_flag=d.get('text_generation_flag', 0))
    if len(out) < len(want) + len(want_cast):     # the profile's examples_box belongs to another file: look for the example notes anywhere in this one (on the note layer)
        for e in doc.modelspace().query('TEXT'):
            if e.dxf.layer != PROF['layers']['text']: continue
            for k, raw in {**want, **want_cast}.items():
                if e.dxf.text == raw and k not in out:
                    d = e.dxf; out[k] = dict(style=d.style, height=d.height, width=d.get('width', 1.0), text_generation_flag=d.get('text_generation_flag', 0))
    for k in list(want) + list(want_cast):      # fallback when an example text is missing
        out.setdefault(k, dict(style='MIRYL' if k in ('bt', 'tp', 'pp') else 'HEBREW_NEW', height=6.0, width=1.0))
    return out

def clear_detail_dims(doc, box):
    """Delete the dimensions of the detail row inside box = (x0, y0, x1, y1). The box x-range stops short of loose items the user drew beside the row."""
    msp = doc.modelspace(); x0, y0, x1, y1 = box; n = 0
    for e in list(msp.query('DIMENSION')):
        if e.dxf.layer != PROF['layers']['text']: continue
        c = e.dxf.defpoint
        if x0 < c.x < x1 and y0 < c.y < y1:
            blk = e.dxf.geometry; msp.delete_entity(e)
            try: doc.blocks.delete_block(blk, safe=False)
            except Exception: pass
            n += 1
    return n

def clear_cell(doc, box):
    """Delete what earlier runs drew inside the cell: outline lines/polylines, dimensions (+anon blocks), 'o.k block'. Keeps the frame, titles, user markup."""
    msp = doc.modelspace(); x0, y0, x1, y1 = box; n = 0
    for e in list(msp):
        try: b = bbox.extents([e])
        except Exception: continue
        if not b.has_data or not (x0 < b.center.x < x1 and y0 < b.center.y < y1): continue
        t, lay = e.dxftype(), e.dxf.layer
        if lay in ('72_MISGERET_WIN', 'SHINUIM-TIKUNIM', 'claude'): continue       # frames and the user's own markup (red clouds on layer claude) are never cleared
        if t == 'TEXT':
            raw = e.dxf.text
            if not (raw.startswith(PROF['title']['prefix']) or raw == PROF['title']['scale_text']['text']): msp.delete_entity(e); n += 1     # old notes; keep title and 1:25
            continue
        if t == 'DIMENSION':
            blk = e.dxf.geometry; msp.delete_entity(e)
            try: doc.blocks.delete_block(blk, safe=False)
            except Exception: pass
            n += 1
        elif t in ('LINE', 'LWPOLYLINE', 'CIRCLE', 'LEADER') or (t == 'INSERT' and (e.dxf.name in ('o.k block', 'dot barzel', 'MH') or e.dxf.name.startswith('*U'))): msp.delete_entity(e); n += 1     # user 2026-10-22: stale 'dot barzel' dots + LEADERs of an earlier draw gave a DOUBLE reinforcement     # incl. anonymous blocks of hand-made stirrup details
    return n

def main():
    a = argparse.ArgumentParser(); a.add_argument('file'); a.add_argument('name'); a.add_argument('--profile', default='israeli-structural')
    a.add_argument('--box', nargs=4, type=float, help='X0 Y0 W H of the target cell'); a.add_argument('--cell', help="N (1-based, left to right) or 'auto' (first free cell): take the box from the user's white cells instead of --box"); a.add_argument('--beam', nargs=2, type=float, required=True)
    a.add_argument('--slab', type=float, required=True, help='ledge kind: hollow-core thickness; cast kind: total slab D'); a.add_argument('--topping', type=float, default=0); a.add_argument('--slab-left', type=float); a.add_argument('--slab-right', type=float); a.add_argument('--sides', choices=['both', 'right', 'left', 'none'], default='right'); a.add_argument('--kind', choices=['ledge', 'cast'], default='ledge', help='ledge = hollow-core on ledges (ex 2-2 / 5-5); cast = cast L edge beam (ex 1-1)')
    a.add_argument('--identical', type=int, help='N beams share this section: writes the note זהה ל-N קורות under the scale text'); a.add_argument('--h-label', help="untagged beam: write this SYMBOL (e.g. 'h') on the height dimensions instead of numbers"); a.add_argument('--solid', choices=['left', 'right'], help='SOLID (cast) slab on the side without a ledge (plan label D=nn without +topping)'); a.add_argument('--solid-D', type=float, default=0.0); a.add_argument('--solid-label', help="symbol (e.g. 'H') written on the solid slab's thickness dimension instead of the number"); a.add_argument('--solid-drop', type=float, default=0.0, help='level step: solid slab top this far BELOW the beam top (hollow slab level - solid slab level)'); a.add_argument('--stirrups', choices=['standard', 'transfer'], default='standard', help="stirrup table: standard beams (Φ12@15) or TRANSFER beams (carry a new element rising from them; Φ12/14/16@15)")
    a.add_argument('--detail', choices=['none', 'plan', 'ss'], default='none', help="none = the full example detail; plan = S mark (as per plan); ss = SS mark (engineer chooses)"); a.add_argument('--replace', action='store_true'); a.add_argument('--dims-only', action='store_true', help='only redraw the stirrup-detail dimensions (keeps everything else, e.g. the user\'s hand edits)'); a.add_argument('-o'); a.add_argument('--dry', action='store_true'); a.add_argument('--png')
    a = a.parse_args(); apply_profile(a.profile); a.note = ('זהה ל-%d קורות' % a.identical) if a.identical and a.identical > 1 else None; run(a)

def run(a, doc=None):
    """Draw one section described by the argparse-like namespace `a` (see main). doc given: draw into that open document and do not save (batch use, see recipes/plan_sections.py)."""
    global STIRRUPS, STIRRUP_SPACING, H_SYM, SOLID_SYM
    SOLID_SYM = getattr(a, 'solid_label', None) or None
    H_SYM = getattr(a, 'h_label', None) or None
    STIRRUPS = getattr(a, 'stirrups', 'standard') or 'standard'; STIRRUP_SPACING = load_profile(getattr(a, 'profile', 'israeli-structural') or 'israeli-structural')['stirrup_tables'][STIRRUPS]['note']
    # only the tall-stirrup detail note (n + table note) carries the table diameter (ST: 12/14/16); the section note $12@20 and the U note $12@15 stay $12 (user 2026-10-21, red cloud on 14-14)
    if a.cell:
        d0 = ezdxf.readfile(a.file); ex = PROF.get('examples_box', [1e12] * 4)
        cells = [c for c in target_cells(d0, PROF['layers']['target_cell']) if not (c[0] < ex[2] and c[2] > ex[0] and c[1] < ex[3] and c[3] > ex[1])]     # not the example sheet frame
        pick = next((c for c in cells if c[4]), None) if a.cell == 'auto' else (cells[int(a.cell) - 1] if 0 < int(a.cell) <= len(cells) else None)
        if not pick: sys.exit(f'no target cell for --cell {a.cell} ({len(cells)} cells, free: {[i + 1 for i, c in enumerate(cells) if c[4]]})')
        a.box = [pick[0], pick[1], pick[2] - pick[0], pick[3] - pick[1]]; print('target cell', [round(v) for v in a.box])
    if not a.box: sys.exit('give --box X0 Y0 W H or --cell N|auto')
    W, H = a.beam; bx0, by0, bw, bh = a.box; oy = by0 + (getattr(a, 'beam_bottom', None) or PROF['outline']['cell_beam_bottom_y'])
    B_ = W
    if a.kind == 'cast':
        g = build_cast(W, H, a.slab, a.topping or 5.0, a.sides == 'both', a.slab_left, none=(a.sides == 'none'), solid_D=(getattr(a, 'solid_D', 0.0) if getattr(a, 'solid', None) else 0.0)); lo, hi = (g['endL'] - 30 - (22 if g.get('solid') else 0) if (g['both'] or g.get('solid')) else -14.0), (B_ + 60 if g['none'] else g['end'] + 30)
        mir = a.sides == 'left'                                       # slab on the left of the view (user's marker on a south edge beam looking E): mirror image of example 1-1
        if mir: lo, hi = W - hi, W - lo
        ox = bx0 + bw / 2 - (lo + hi) / 2
        print(f"{a.name}: cast edge beam {W:.0f}x{H:.0f}, slab D={a.slab:.0f}; dots {len(g['dots'])}")
        if a.dry: return
        nosave = doc is not None; doc = doc or ezdxf.readfile(a.file); a.nosave = nosave; tmpl = template_texts(doc)
        if a.replace: print('cleared', clear_cell(doc, (bx0, by0, bx0 + bw, by0 + bh)), 'old entities')
        draw_cast(doc, g, ox, oy, tmpl, mirror=mir); finish(doc, a, ox, oy, W, H, (lo + hi) / 2, (W / 2 + 9.5) if g['none'] else (-(CAST_SLAB_END - 14) if mir else W + 0.7)); return
    g = build(W, H, a.slab, a.topping, a.sides, a.slab_left, a.slab_right, getattr(a, 'solid', None), getattr(a, 'solid_D', 0.0), getattr(a, 'solid_drop', 0.0)); ox = bx0 + bw / 2 - (g['xl'] + g['xr']) / 2
    if a.dims_only:
        doc = ezdxf.readfile(a.file); tmpl = template_texts(doc); n = clear_detail_dims(doc, (ox - 100, by0, ox + W + 100, oy - 60))
        draw_details(doc, tmpl, ox, oy, g['tall'], g['left'], g['right'], H, g['hbL'], g['hbR'], W, dims_only=True); print('restyled detail dims, removed', n)
        out = a.o or a.file
        if out == a.file: backup(a.file, 'ledge-' + a.name)
        doc.saveas(out); print('saved', out, '| audit errors', len(ezdxf.readfile(out).audit().errors)); return
    print(f"{a.name}: beam {W:.0f}x{H:.0f}, hollow-core {a.slab:.0f} + topping {a.topping:.0f}, slab {a.sides}; below ledge {g['hb']:.0f}; dots {len(g['dots'])} (bottom {len(g['rows']['bot'])}, top {len(g['rows']['top'])}); stem stirrups {len(g['tall'])}")
    if a.dry: return
    nosave = doc is not None; doc = doc or ezdxf.readfile(a.file); a.nosave = nosave; tmpl = template_texts(doc)
    if a.replace: print('cleared', clear_cell(doc, (bx0, by0, bx0 + bw, by0 + bh)), 'old entities')
    draw(doc, g, ox, oy, a.name, tmpl)
    finish(doc, a, ox, oy, W, H, (g['xl'] + g['xr']) / 2, (g['xs0'] - 3.3) if g['left'] else (W / 2 + PROF['level_marker']['dx_from_beam_centre']))

SS_NOTES = ('c/g/ kph ,fbh,', 'c/,/ kph ,fbh,', 'c/g/ kph ,fw', 'c/,/ kph ,fw')
PLAN_NOTE = {'4$12': 'c/g/ kph ,fw', '2$12': 'c/,/ kph ,fw'}     # beam bar callouts of a cast / general beam -> 'as per plan' (user's hand fix of 8-8, 2026-10-16)

class _Seg:
    """a horizontal 56_HATAH_ZET shelf, LWPOLYLINE or LINE, with a uniform get / set"""
    def __init__(self, e):
        self.e = e
        if e.dxftype() == 'LINE': (self.x1, self.y), (self.x2, _) = (e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)
        else: (self.x1, self.y), (self.x2, _) = [(p[0], p[1]) for p in e.get_points('xy')]
    def set(self, xs, xe):
        if self.e.dxftype() == 'LINE': self.e.dxf.start = (xs, self.y, 0); self.e.dxf.end = (xe, self.y, 0)
        else: self.e.set_points([(xs, self.y), (xe, self.y)])

def _shelf(msp, x_end, y, box, tol=4.5):
    """the 2-point horizontal 56_HATAH_ZET shelf of a note (polyline or line): its end near x_end (+-tol) at height y (+-4)"""
    bx0, by0, bw, bh = box
    for e in msp.query('LWPOLYLINE LINE'):
        if e.dxf.layer != '56_HATAH_ZET' or (e.dxftype() == 'LWPOLYLINE' and len(e) != 2): continue
        sg = _Seg(e); y2 = e.dxf.end.y if e.dxftype() == 'LINE' else [p[1] for p in e.get_points('xy')][1]
        if abs(sg.y - y2) < 0.01 and bx0 < min(sg.x1, sg.x2) < bx0 + bw and abs(sg.y - y) < 4.0 and abs(max(sg.x1, sg.x2) - x_end) < tol: return sg
    return None

def title_name(name):
    """section title text: every number is written digit-REVERSED (the mirrored Hebrew font shows it right): '10-10' -> '01-01', '12-12' -> '21-21' (user's gallery + his fix of 10-10, 2026-10-16)"""
    import re
    return re.sub(r'\d+', lambda m: m.group()[::-1], name)

def apply_detail(doc, a):
    """S / SS marks (user 2026-10-16). Learned from his hand fixes of 8-8 (S) and 9-9 (SS):
    SS = the engineer picks the bars: the two slab-bar leader notes read 'X$XX' (HEBREW_NEW, width 0.8, left-aligned, inset ~9 on the shelf) and the shelf is cut to 2 x the text width (34.3).
    S  = 'as per plan': the beam's own bar callouts '4$12' (top) / '2$12' (bottom) of a cast / general beam become the per-plan notes ('c/g/ kph ,fw' / 'c/,/ kph ,fw', mirrored SIVAN 0.7) on a shelf lengthened to 46.2 (top) / 47.1 (bottom) (text right end ~2.8 inside the end);
    the forks to the beam's own bars STAY (user 2026-10-21: leaders point to the relevant bars; the 8-8 fix had left an orphan shelf). Works on the TEXT inside a.box; returns the number of notes changed."""
    msp = doc.modelspace(); bx0, by0, bw, bh = a.box; n = 0
    texts = [t for t in msp.query('TEXT') if bx0 < t.dxf.insert.x < bx0 + bw and by0 - 120 < t.dxf.insert.y < by0 + bh + 170]       # a tall beam (230) reaches ~100 above the standard box
    if getattr(a, 'detail', 'none') == 'ss' and any(t.dxf.text == '4$12' for t in texts):
        # SS on a CAST / general beam (user's hand fix of 11-11): the diameter goes on the BEAM (bar callouts 4$12 and 2$12 -> X$XX), the slab-bar notes read 'reinforcement per plan'
        # (' zhui kph ,fbh,', MIRYL 6) on a shelf lengthened OUTWARD (left 63.8, right 66.1); text at the shelf end +4.7 (left) / +0.8 (right). BOTH beam callouts (4$12 top, 2$12 bottom) become X$XX (his 12-12 fix confirmed the bottom one).
        cx = [t.dxf.insert.x for t in texts if t.dxf.text == '4$12'][0]
        for t in texts:
            if t.dxf.text in ('4$12', '2$12'): t.dxf.text = 'X$XX'; n += 1
            elif t.dxf.text in ('c/g/ kph ,fw', 'c/,/ kph ,fw'):
                sh = _shelf(msp, t.dxf.insert.x, t.dxf.insert.y - 1.4, a.box) or _shelf(msp, t.dxf.insert.x, t.dxf.insert.y - 1.5, a.box)
                if sh is None: continue
                lo, hi = min(sh.x1, sh.x2), max(sh.x1, sh.x2)
                if t.dxf.insert.x < cx: sh.set(hi - 63.8, hi); tx = hi + 4.7
                else: sh.set(lo, lo + 66.1); tx = lo + 66.1 + 0.8
                t.dxf.text = ' zhui kph ,fbh,'; t.dxf.style = 'MIRYL'; t.dxf.text_generation_flag = 0; t.dxf.insert = (tx, sh.y + 1.1)
                t.dxf.discard('width')
                n += 1
        return n
    if getattr(a, 'detail', 'none') == 'ss':
        for t in texts:
            if t.dxf.text not in SS_NOTES: continue
            sh = _shelf(msp, t.dxf.insert.x, t.dxf.insert.y - 1.4, a.box) or _shelf(msp, t.dxf.insert.x, t.dxf.insert.y - 2.8, a.box)
            if sh is None: continue
            xs = min(sh.x1, sh.x2); sh.set(xs, xs + 34.3)
            t.dxf.text = 'X$XX'; t.dxf.style = 'HEBREW_NEW'; t.dxf.width = 0.8; t.dxf.text_generation_flag = 0; t.dxf.insert = (xs + 9.0, t.dxf.insert.y); n += 1
        return n
    if getattr(a, 'detail', 'none') != 'plan': return 0
    for t in texts:                                           # S: per-plan notes instead of the beam bar callouts
        if t.dxf.text not in PLAN_NOTE: continue
        top = t.dxf.text == '4$12'; xs = t.dxf.insert.x - (3.4 if top else 2.9); y = t.dxf.insert.y - 0.7
        sh = _shelf(msp, xs + (23.6 if top else 21.9), y, a.box, 1.0)
        if sh is None: continue
        L = 46.2 if top else 47.1; sh.set(xs, xs + L)
        t.dxf.text = PLAN_NOTE[t.dxf.text]; t.dxf.style = 'SIVAN'; t.dxf.width = 0.7; t.dxf.text_generation_flag = 2; t.dxf.insert = (xs + L - (2.9 if top else 2.7), y + (2.1 if top else 1.2)); n += 1
    return n

def finish(doc, a, ox, oy, W, H, centre, tipx):
    """Re-centre this section's title + scale text, add the 'o.k per plan' marker (arrow tip at tipx), save, audit, render."""
    apply_detail(doc, a); bx0, by0, bw, bh = a.box; cx = ox + centre; T_ = PROF['title']
    import rebar_color; rebar_color.colour_box(doc, (bx0, by0 - 120, bw, bh + 290))       # rebar (57_HATAH_ZIUN) blue, layers unchanged (user 2026-10-21)
    import sivan_text; sivan_text.convert_box(doc, (bx0, by0 - 120, bw, bh + 290))       # Hebrew notes in SIVAN (user 2026-10-21: HEBREW_NEW notes were unreadable)
    import leader_fit; leader_fit.fit_box(doc, (bx0, by0 - 120, bw, bh + 290))       # shelf = text width, forks on the bars (user 2026-10-21)
    msp = doc.modelspace(); have = [e.dxf.text for e in msp.query('TEXT') if bx0 < e.dxf.insert.x < bx0 + bw and by0 < e.dxf.insert.y < by0 + bh and e.dxf.layer == PROF['layers']['text']]
    if not any(t.startswith(T_['prefix']) for t in have):          # new cell: create the title + scale text like the user's (SIVAN mirrored, HEBREW_NEW)
        msp.add_text(T_['prefix'] + title_name(a.name), height=T_['height'], dxfattribs=dict(layer=PROF['layers']['text'], style=T_['style'], width=T_['width'], text_generation_flag=T_['text_generation_flag'], insert=(cx + T_['dx_from_centre'], oy + H + T_['dy_above_top'])))
        st = T_['scale_text']; msp.add_text(st['text'], height=st['height'], dxfattribs=dict(layer=PROF['layers']['text'], style=st['style'], width=st['width'], insert=(cx + st['dx_from_centre'], oy + H + st['dy_above_top'])))
    note = getattr(a, 'note', None)
    if note:                                                         # e.g. 'identical for N beams' under the scale text
        st = T_['scale_text']; msp.add_text(encode(note), height=6, dxfattribs=dict(layer=PROF['layers']['text'], style='MIRYL', insert=(cx + st['dx_from_centre'], oy + H + st['dy_above_top'] - 14)))
    for e in doc.modelspace().query('TEXT'):
        if bx0 < e.dxf.insert.x < bx0 + bw and by0 < e.dxf.insert.y < by0 + bh and e.dxf.layer == PROF['layers']['text']:
            if e.dxf.text.startswith(T_['prefix']): e.dxf.insert = (cx + T_['dx_from_centre'], oy + H + T_['dy_above_top'])
            elif e.dxf.text == T_['scale_text']['text']: e.dxf.insert = (cx + T_['scale_text']['dx_from_centre'], oy + H + T_['scale_text']['dy_above_top'])
    M = PROF['level_marker']
    if M['block'] in doc.blocks:      # ex 2-2: tip 3.3 left of the stem's left face; ex 1-1: 0.7 right of the stem; else as the user placed it on the L sections
        doc.modelspace().add_blockref(M['block'], (ox + tipx - M['tip_in_block'][0], oy + H - M['tip_in_block'][1]), dxfattribs=dict(layer=PROF['layers']['level_marker']))
    if getattr(a, 'nosave', False): return
    out = a.o or a.file
    if out == a.file: backup(a.file, 'ledge-' + a.name)
    doc.saveas(out); print('saved', out, '| audit errors', len(ezdxf.readfile(out).audit().errors))
    if a.png: render_png(doc, (ox + centre - 190, ox + centre + 190, oy - 50, oy + H + 100), a.png)

if __name__ == '__main__': main()
