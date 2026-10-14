"""Overlap audit of dimension texts (read-only): text-text, text over another dim's extension line, text over another line's dimension line.
  python plan_overlaps.py FILE --box X0 Y0 X1 Y1 [-o report.txt]   (user rule 2026-10-13: plan must be clear, nothing overlapping; goal = 0 / 0 / 0, user's own texts excepted)
Text box = dimtxt, 0.6 x height per character."""
import ezdxf, sys, collections, argparse
ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, required=True); ap.add_argument('-o', default='plan_overlaps.txt'); a = ap.parse_args()
f = a.file; out = open(a.o, 'w', encoding='utf-8')
doc = ezdxf.readfile(f); msp = doc.modelspace()
st = doc.dimstyles.get('dim_100'); TH = st.dxf.dimtxt; print('dimtxt', TH, 'dimscale', st.dxf.get('dimscale', 1), file=out)
box = tuple(a.box)
D = []
for e in msp.query('DIMENSION'):
    if e.dimtype & 7 != 0: continue
    p, a, b, t = e.dxf.defpoint, e.dxf.defpoint2, e.dxf.defpoint3, e.dxf.text_midpoint
    if not (box[0] <= p.x <= box[2] and box[1] <= p.y <= box[3]): continue
    ang = e.dxf.get('angle', 0) % 180; m = abs(a.x - b.x) if ang < 1 else abs(a.y - b.y)
    txt = '%d' % round(m); w = 0.6 * TH * len(txt) + 4; h = TH + 4
    if ang < 1:
        tb = (t.x - w / 2, t.y - h / 2, t.x + w / 2, t.y + h / 2); ext = [((a.x, a.y), (a.x, p.y)), ((b.x, b.y), (b.x, p.y))]; dl = ((min(a.x, b.x), p.y), (max(a.x, b.x), p.y)); ax = 'X'
    else:
        tb = (t.x - h / 2, t.y - w / 2, t.x + h / 2, t.y + w / 2); ext = [((a.x, a.y), (p.x, a.y)), ((b.x, b.y), (p.x, b.y))]; dl = ((p.x, min(a.y, b.y)), (p.x, max(a.y, b.y))); ax = 'Y'
    D.append(dict(h=e.dxf.handle, ax=ax, tb=tb, ext=ext, dl=dl, m=m, own=e.has_xdata('CLAUDE_ROWS'), line=round(p.y if ax == 'X' else p.x)))
print('dims', len(D), file=out)
def ov(a, b): return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]
def seg_hit(tb, s):
    (x0, y0), (x1, y1) = s; lo = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    return lo[0] <= tb[2] and lo[2] >= tb[0] and lo[1] <= tb[3] and lo[3] >= tb[1]
tt = []; te = []; tl = []
for i, d in enumerate(D):
    for j in range(i + 1, len(D)):
        if ov(d['tb'], D[j]['tb']): tt.append((d['h'], D[j]['h'], d['line'], D[j]['line'], round(d['tb'][0]), round(d['tb'][1])))
    for j, o in enumerate(D):
        if j == i: continue
        if any(seg_hit(d['tb'], s) for s in o['ext']) and (o['line'] != d['line'] or o['ax'] != d['ax']): te.append((d['h'], o['h'], d['line'], o['line'], round(d['tb'][0]), round(d['tb'][1])))
        if o['line'] != d['line'] and seg_hit(d['tb'], o['dl']): tl.append((d['h'], o['h'], d['line'], o['line'], round(d['tb'][0]), round(d['tb'][1]), d['own'], o['own']))
print('text-text overlaps', len(tt), file=out); [print('  ', x, file=out) for x in tt[:25]]
print('text over another line\'s extension line', len(te), file=out); [print('  ', x, file=out) for x in te[:25]]
print('text over another dim line', len(tl), tl[:6], file=out)
