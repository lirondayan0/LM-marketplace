"""Recipe: reinforcement for XREF sections that are NOT a plain beam: WALL + SLAB junctions (user 2026-10-23: 'there is no such thing as a wall, beam or slab without reinforcement in its cross-section;
use your judgment'). 3841-CON_test Sec 22, 26, 30, 31, 32 (no S-BEAM-1 outline or a wall beside the beam). Engineering reading of the XREF:
  wall  = pair of A-WALL-1 verticals 15-30 apart (extent = both lines); slab = pair of A-FLOR-1 horizontals 25-45 apart; stem = S-BEAM-1 bounding box (beam / nib beside the wall).
  WALL  : vertical bars on both faces (axis 2.9 / 3.0 from the face, straight, to the cut ends; a wall top flush with a slab = ends 3 below the top with 14 hooks into the wall, like his Sec 9 C bar),
          horizontal bars = two dot columns at 4.2 from the faces, equal steps <= 16.1 (xref_wall), notes: wall note ('wall reinforcement per plan', his template) + '$8@15' on both vertical bars (his Sec 9 number).
  SLAB  : the general_beam slab convention - bottom bar at soffit+3 entering the wall min(60, t-3), top bar at top-3 running to the far face of the wall with a hook DOWN (anchorage), dot rows 4 per side step 15 first 9.9
          from the face at top-4.3 / soffit+4.4, notes 'top / bottom per plan'.
  STEM  : general_beam.draw(sides=...) - stirrups from the user's table, side steel by area, bar dots, slab bars only on the side that has a slab.
Everything is UNVERIFIED engineering judgment (rule 9: numbers copied from his Sec 9 / general_beam, nothing invented); the user corrects with clouds."""
import math
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'scripts')); from dxflib import XREF_ROLE_LAYERS as RL      # Revit layer names by role
import ledge_beam as LB
import general_beam as GB
import xref_wall as XW

Z = '56_HATAH_ZET'; RB = '57_HATAH_ZIUN'; T = '54_HATAH_TEXT'

def lay(e): return e.dxf.layer.split('$0$')[-1]

def read(doc, ins):
    ix, iy = ins.dxf.insert.x, ins.dxf.insert.y; L = [s for s in doc.blocks.get(ins.dxf.name) if s.dxftype() == 'LINE']
    seg = lambda s: (s.dxf.start.x + ix, s.dxf.start.y + iy, s.dxf.end.x + ix, s.dxf.end.y + iy)
    W = [seg(s) for s in L if lay(s) in RL['wall']]; F = [seg(s) for s in L if lay(s) in RL['floor']]; Bm = [seg(s) for s in L if lay(s) in RL['beam']]; C = [seg(s) for s in L if lay(s) == 'A-FLOR-MCUT']
    walls = []
    xs = sorted({round(a, 1) for a, b, c, d in W if abs(a - c) < 0.05})
    used = set()
    for i, x0 in enumerate(xs):
        if i in used: continue
        for j in range(i + 1, len(xs)):
            if 14 <= xs[j] - x0 <= 31 and j not in used:
                ys = [v for a, b, c, d in W if abs(a - c) < 0.05 and round(a, 1) in (x0, xs[j]) for v in (b, d)]
                walls.append(dict(xl=x0, xr=xs[j], y0=min(ys), y1=max(ys))); used |= {i, j}; break
    stem = None
    if Bm:
        sx = [v for a, b, c, d in Bm for v in (a, c)]; sy = [v for a, b, c, d in Bm for v in (b, d)]; stem = dict(x0=min(sx), x1=max(sx), y0=min(sy), y1=max(sy))
    hs = sorted({(round(b, 1), min(a, c), max(a, c)) for a, b, c, d in F if abs(b - d) < 0.05 and abs(a - c) > 40})
    slabs = []; usedh = set()
    for i, (yt, xa, xb) in enumerate(hs):
        if i in usedh: continue
        for j, (ys, xa2, xb2) in enumerate(hs):
            if j != i and j not in usedh and 25 <= yt - ys <= 45 and abs(xa - xa2) < 1 and abs(xb - xb2) < 1:
                topping = next((yt - b for a, b, c, d in C if abs(a - c) > 40 and abs(min(a, c) - xa) < 1 and abs(max(a, c) - xb) < 1), 5.0)
                slabs.append(dict(top=yt, soffit=ys, xa=xa, xb=xb, T=topping)); usedh |= {i, j}; break
    return dict(walls=walls, stem=stem, slabs=slabs)

def slab_side(sl, anchor_x):
    """'right' when the slab lies right of anchor_x (wall centre / stem centre)"""
    return 'right' if (sl['xa'] + sl['xb']) / 2 > anchor_x else 'left'

def dot(msp, x, y, sgn):
    msp.add_lwpolyline([(x - sgn * GB.DOT_LEN / 2, y, 0, 0, -sgn), (x + sgn * GB.DOT_LEN / 2, y, 0, 0, -sgn)], format='xyseb', close=True, dxfattribs=dict(layer=RB, const_width=GB.DOT_W))

def draw_slab(doc, tmpl, msp, sl, u, xface, xfar, name=''):
    """u = +1 right slab, -1 left; xface = slab end at the wall, xfar = far face of the wall (bars anchor into it)"""
    top, soff = sl['top'], sl['soffit']; D = top - soff; xend = sl['xb'] if u > 0 else sl['xa']; t = abs(xfar - xface)
    anc = min(60.0, t - 3.0); hook = min(25.0, D - 6.0)
    msp.add_lwpolyline([(xend, soff + 3), (xface - u * anc, soff + 3)], dxfattribs=dict(layer=RB))                       # bottom bar into the wall
    msp.add_lwpolyline([(xend, top - 3), (xfar - u * 3.0, top - 3), (xfar - u * 3.0, top - 3 - hook)], dxfattribs=dict(layer=RB))   # top bar through the wall face with a hook DOWN
    for y in (top - GB.TOP_IN, soff + GB.SOFFIT_IN):
        for k in range(GB.DOT_N): dot(msp, xface + u * (GB.DOT_FIRST + GB.DOT_STEP * k), y, u)
    def txt(raw, key, x, y):
        a = dict(tmpl[key]); a.update(layer=T, insert=(x, y)); msp.add_text(raw, height=a.pop('height'), dxfattribs=a)
    ex, ey = xface + u * 28.8, top + 5.6
    msp.add_line((xface + u * 10.5, top - GB.TOP_IN), (ex, ey), dxfattribs=dict(layer=Z)); msp.add_line((xface + u * 21.9, top - 3), (ex, ey), dxfattribs=dict(layer=Z))
    msp.add_line((ex, ey), (ex + u * 45.3, ey), dxfattribs=dict(layer=Z)); txt('c/g/ kph ,fw', 'tp_cast', (ex + 43.9) if u > 0 else (ex - 1.4), ey + 1.5)      # mirrored text hangs LEFT of its insert point: at the shelf end (right slab) / at the joint (left slab), as general_beam
    y2 = soff + GB.SOFFIT_IN; ex, ey = xface + u * 19.8, y2 - 16.7
    msp.add_line((xface + u * 15.6, soff + 3), (ex, ey), dxfattribs=dict(layer=Z)); msp.add_line((xface + u * 9.9, y2), (ex, ey), dxfattribs=dict(layer=Z))
    msp.add_line((ex, ey), (ex + u * 45.0, ey), dxfattribs=dict(layer=Z)); txt('c/,/ kph ,fw', 'bt_cast', (ex + 44.4) if u > 0 else (ex - 1.6), ey + 1.2)

def draw_wall(doc, w, slabs, tmpl, top_flush, name=''):
    msp = doc.modelspace(); xl, xr, y0, y1 = w['xl'], w['xr'], w['y0'], w['y1']; XL, XR = xl + 2.9, xr - 3.0
    yt = y1 - 3.0 if top_flush else y1
    for x, d in ((XL, 1), (XR, -1)):
        pts = [(x, y0), (x, yt)] + ([(x + d * XW.HOOK, yt)] if top_flush else [])
        msp.add_lwpolyline(pts, dxfattribs=dict(layer=RB))
    ys = y0 + 4.6; ye = y1 - 4.2; n = max(2, math.ceil((ye - ys) / XW.STEP_H - 1e-9) + 1)
    for x in (xl + XW.COV_D, xr - XW.COV_D):
        for i in range(n): dot(msp, x, ys + (ye - ys) * i / (n - 1), 1)
    # notes on the side that has no slab around the chosen height
    def free(side, ytip):
        for s in slabs:
            sd = 'right' if (s['xa'] + s['xb']) / 2 > (xl + xr) / 2 else 'left'
            if sd == side and s['soffit'] - 30 < ytip < s['top'] + 30: return False
        return True
    ytip = y0 + 0.69 * (y1 - y0)
    for cand in (0.69, 0.5, 0.8, 0.35, 0.9, 0.2):
        ytip = y0 + cand * (y1 - y0)
        if free('left', ytip) or free('right', ytip): break
    side = 'left' if free('left', ytip) else 'right'; u = -1 if side == 'left' else 1; face = xl if u < 0 else xr
    tipx = face - u * XW.COV_D; ey = ytip - 14.3; ex = tipx + u * 33.5
    msp.add_lwpolyline([(tipx, ytip), (ex, ey), (ex + u * 36.9, ey)], dxfattribs=dict(layer=Z))
    for raw, dy, dx in (('zhui ehru,', 3.0, 2.5), ('zhui  kph ', 12.0, -1.3)):
        msp.add_text(raw, dxfattribs=dict(layer=T, style='SIVAN', height=6.0, width=0.8, text_generation_flag=2, insert=((ex + dx) if u < 0 else (ex + 36.9 - dx), ey + dy)))
    # '$8@15' on both vertical bars (his Sec 9 number), shelf on the same side, 30 below the wall note
    by = ytip - 40.0
    if y0 + 8 < by < y1 - 8:
        jx = face + u * 7.6; jy = by
        msp.add_lwpolyline([(jx, jy), (jx + u * 20.2, jy)], dxfattribs=dict(layer=Z)); msp.add_line((jx, jy), (XL, by - 1.5), dxfattribs=dict(layer=Z)); msp.add_line((jx, jy), (XR, by - 1.5), dxfattribs=dict(layer=Z))
        msp.add_text('2$8@15', dxfattribs=dict(layer=T, style='HEBREW_NEW', height=6.0, width=0.8, insert=(jx + 2.0 if u > 0 else jx - 19.2, jy + 1.0)))
    return n

def draw_section(doc, num, ins, tmpl, kind='S'):
    """returns a short report; draws everything for one wall / slab / stem XREF section"""
    msp = doc.modelspace(); R = read(doc, ins); rep = dict(num=num, walls=len(R['walls']), slabs=len(R['slabs']), stem=bool(R['stem']))
    if not R['walls']: raise ValueError('no wall found')
    w = R['walls'][0]; wc = (w['xl'] + w['xr']) / 2
    LB.apply_profile('israeli-structural'); LB.OVERLAY = True; GB.OVERLAY = True
    st = R['stem']
    if st:
        B, H = st['x1'] - st['x0'], st['y1'] - st['y0']
        # the stem hangs beside the wall; its slab = the slab on the stem's side (nearest to it)
        sl = [s for s in R['slabs'] if min(abs(s['xb'] - st['x0']), abs(s['xa'] - st['x1']), abs(s['xb'] - st['x1']), abs(s['xa'] - st['x0'])) < 1 or s['xa'] - 1 <= st['x0'] <= s['xb'] + 1]
        s0 = sl[0] if sl else R['slabs'][0]
        stem_c = (st['x0'] + st['x1']) / 2; sd = 'left' if (s0['xa'] + s0['xb']) / 2 < stem_c else 'right'
        top_s = s0['top']; D_ = top_s - s0['soffit']
        if abs(st['y1'] - s0['soffit']) < 0.5: H = top_s - st['y0']      # the XREF outline of the stem stops at the slab soffit: the beam top is the slab top (as xref_overlay does)
        dl = st['y0'] + H - top_s
        lab = {'B': None, 'H': None, 'D': None, 'B-6': None, 'H-6': None}
        kw = dict(Dl=D_, Dr=D_, dl=dl, dr=dl)
        LB.STIRRUPS = 'transfer' if kind == 'ST' else 'standard'
        GB.draw(doc, B, D_, H, st['x0'], st['y0'], f'{num}-{num}', tmpl, lab, 0.0, LB.STIRRUPS, sides=sd, **kw)
        rep['stem_B_H'] = (round(B), round(H)); R['slabs'] = [s for s in R['slabs'] if s is not s0]
    flush = any(abs(s['top'] - w['y1']) < 0.5 for s in R['slabs'] + ([s0] if st and sl else [])) or bool(st)
    n = draw_wall(doc, w, R['slabs'] + ([s0] if st and sl else []), tmpl, top_flush=flush, name=num)
    rep['wall_dots'] = 2 * n
    for s in R['slabs']:
        u = 1 if slab_side(s, wc) == 'right' else -1
        draw_slab(doc, tmpl, msp, s, u, w['xr'] if u > 0 else w['xl'], w['xl'] if u > 0 else w['xr'])
    return rep
